'''
    File: train.py
    Author : Tawn Kramer
    Date : July 2017
'''
import os
import sys
import numpy as np
import cv2
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.models import load_model
from sklearn.model_selection import train_test_split
from sklearn.utils import shuffle
import glob
import models
import argparse

def prepare_mask(mimg, opt):
    '''
    Take an RGB image where different classes of pixels all share a color
    from the list of class_colors. Then create a matrix with a mask for each
    class using the threshold value passed in. Returns the numpy array of masks.
    '''
    comb_classes = opt['combined_classes']
    class_colors = opt['class_colors']
    num_classes = opt['nb_classes']
    
    width = mimg.shape[1]
    height = mimg.shape[0]
    mask_image = np.zeros([height, width, num_classes], dtype=np.dtype('B'))
    iClass = 0
    for key, value in comb_classes.items():
        mask_ch = None

        for col_indx_low, col_indx_hi in value:
            col_low = class_colors[col_indx_low]
            col_hi = class_colors[col_indx_hi]
            lower = np.array(col_low)
            upper = np.array(col_hi)
            mask = cv2.inRange(mimg, lower, upper)

            if mask_ch is None:
                mask_ch = np.zeros_like(mask)
                mask_ch[mask > 0] = 1
            else:
                mask_ch_add = np.zeros_like(mask)
                mask_ch_add[mask > 0] = 1
                mask_ch = np.add(mask_ch, mask_ch_add)
              
        mask_image[..., iClass] = np.reshape(mask_ch, (height, width))
        iClass += 1

    return mask_image


def generator(samples, opt):
    '''
    Rather than keep all data in memory, we will make a function that keeps
    it's state and returns just the latest batch required via the yield command.
    
    We could flip each image horizontally and supply it as a another sample.
    '''
    batch_size = opt['batch_size']
    num_samples = len(samples)
    while 1: # Loop forever so the generator never terminates
        shuffle(samples)
        for offset in range(0, num_samples, batch_size):
            batch_samples = samples[offset:offset+batch_size]

            images_X = []
            images_Y = []

            for batch_sample in batch_samples:
                image_a_path, image_b_path = batch_sample

                image_a = cv2.imread(image_a_path)                
                if image_a is None:
                    continue

                image_b = cv2.imread(image_b_path)
                if image_b is None:
                    continue

                image_a = cv2.cvtColor(image_a, cv2.COLOR_BGR2RGB)
                image_b = cv2.cvtColor(image_b, cv2.COLOR_BGR2RGB)

                image_b = prepare_mask(image_b, opt)
                
                images_X.append(image_a)
                images_Y.append(image_b)

            # final np array to submit to training
            X_train = np.array(images_X)
            y_train = np.array(images_Y)
            yield X_train, y_train


def show_model_summary(model):
    '''
    show the model layer details
    '''
    model.summary()

def get_filenames(opt):
    '''
    using the rgb and mask file path, gather up
    the training files in a tuple of rgb, mask pairs
    '''
    
    rgb_file_mask = opt['rgb_images']
    mask_file_mask = opt['mask_images']
   
    rgbfiles = glob.glob(rgb_file_mask)
    maskfiles = glob.glob(mask_file_mask)
    
    train_files = []

    rgbfiles.sort()
    maskfiles.sort()

    for rgb, mask in zip(rgbfiles, maskfiles):
        train_files.append((rgb, mask))

    return train_files[:opt['limit']]


def make_generators(opt):
    '''
    load the job spec from the csv and create some generator for training
    '''

    lines = get_filenames(opt)

    print("found %d file pairs." % (len(lines)))
    
    train_samples, validation_samples = train_test_split(lines, test_size=0.2)
    
    # compile and train the model using the generator function
    train_generator = generator(train_samples, opt)
    validation_generator = generator(validation_samples, opt)
    
    n_train = len(train_samples)
    n_val = len(validation_samples)
    
    return train_generator, validation_generator, n_train, n_val


def train(opt):
    '''
    Use Keras to train an artificial neural network to use end-to-end behavorial cloning to drive a vehicle.
    '''
    train_generator, validation_generator, n_train, n_val = make_generators(opt)

    model = models.create_model(opt)

    if opt['continue']:
        print('reloading weights')
        model.load_weights(opt['weights_file'])
        for layer in model.layers:
            layer.trainable = True

    show_model_summary(model)

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=10, verbose=0),
        ModelCheckpoint(opt['weights_file'], 
            monitor='val_loss', save_best_only=True, 
            verbose=0, save_weights_only=True),
    ]

    history = model.fit_generator(train_generator, 
        validation_data = validation_generator,
        steps_per_epoch = n_train // opt['batch_size'],
        validation_steps = n_val // opt['batch_size'],
        epochs=opt['epochs'],
        verbose=1,
        callbacks=callbacks)

    print('training complete.')
    model.save_weights(opt['weights_end_file'])


def predict(opt):
    '''
    take and image and use a trained model to segment it
    '''

    model = models.create_model(opt)
    model.load_weights(opt['weights_file'])
    print("num layers:", len(model.layers))
    #from models import load_json_and_weights
    #model = load_json_and_weights('mobilenet_fcnn_mdl.json')

    #from models import save_json_and_weights
    #save_json_and_weights(model, 'mobilenet_fcnn_mdl.h5')
    
    image_path = "./Train/CameraRGB/222.png"

    print("reading image", image_path)
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    print("doing forward pass in image segmentation")
    pred = model.predict(img[None, :, :, :])

    print("pred", pred.shape)

    res = pred[0]
    print("res", res.shape)


    width = img.shape[1]
    height = img.shape[0]
    final_image = np.zeros([height, width, 3], dtype=np.dtype('B'))
    num_classes = opt['nb_classes']

    iClass = 0
    for iClass in range(num_classes):
        channel_data = res[..., iClass]
        print(channel_data.shape)
        final_image[..., iClass] = np.reshape(channel_data, (height, width))

    #image will have 0 or 1, so multiply to view
    final_image = final_image * 255
    
    print("writing %s output" % opt['out'])

    #writes out as 3 channel image
    cv2.imwrite(opt['out'], final_image)


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='train script')
    parser.add_argument('--model', default='model.h5', type=str, help='model name')
    parser.add_argument('--predict', action='store_true', help='do predict test')
    parser.add_argument('--epochs', type=int, default=200, help='number of epochs')
    parser.add_argument('--batch_size', type=int, default=1, help='number samples per batch')
    parser.add_argument('--data_rgb', default="./Train/CameraRGB/*.png", help='data root dir')
    parser.add_argument('--data_mask', default="./Train/CameraSeg/*.png", help='data root dir')
    parser.add_argument('--out', default="prediction_image.png", help='output image filename')
    parser.add_argument('--cont', action='store_true', help='do load previous model')
    
    args = parser.parse_args()

    
    opt         = {'name': 'lanes',
                 'presence_weight': 50.0, 'threshold': 0.5,
                 'original_max_x': 800, 'original_max_y': 600,
                 'crop_min_x': 0, 'crop_max_x': 800,
                 'crop_min_y': 0, 'crop_max_y': 600,
                 'scale_factor': 1}


    '''
    opt['class_colors'] = [
        ([240, 20, 20]), #lane lines
        ([0, 78, 255]), #road
        ([45, 99, 36]), #ground
        ([250, 250, 250]), #sky
    ]
    '''
    
    opt['class_colors'] = [
        ([0, 0, 0]), #sky
        ([1, 0, 0]), #buildings
        ([2, 0, 0]), #?
        ([3, 0, 0]), #?
        ([4, 0, 0]), #?
        ([5, 0, 0]), #?
        ([6, 0, 0]), #lane lines
        ([7, 0, 0]), #street
        ([8, 0, 0]), #sidewalk
        ([9, 0, 0]), #trees
        ([10, 0, 0]), #car
        ([11, 0, 0]), #walls
    ]

    opt['combined_classes'] =\
    {
        1 : [(0, 5), (8, 9), (11, 11)],
        2 : [(6, 7)],
        3 : [(10, 10)]
    }

    '''
    opt['combined_classes'] =\
    {
        1 : [(6, 7)],
        2 : [(10, 10)]
    }
    '''

    #the model saved only when the val_loss improves
    opt['weights_file'] = args.model

    #the model saved when the training finishes, regardless of val_loss
    opt['weights_end_file'] = args.model.replace('.', '_end.')

    opt['nb_classes'] = len(opt['combined_classes'])

    opt['rgb_images'] = args.data_rgb
    opt['mask_images'] = args.data_mask

    opt['input_shape'] = (600, 800, 3)

    opt['epochs'] = args.epochs
    
    opt['batch_size'] = args.batch_size

    opt['out'] = args.out

    opt['continue'] = args.cont

    opt['limit'] = -1 # -1 when all training samples.

    if args.predict:
        predict(opt)
    else:
        train(opt)
