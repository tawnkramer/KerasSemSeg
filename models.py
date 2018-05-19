'''
Models
Define the different NN models we will use
Author: Tawn Kramer
'''
from __future__ import print_function
import os
import tensorflow as tf
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from keras.models import Sequential, Input, Model
from keras.layers import Conv2D, Reshape, Add, UpSampling2D, Multiply, Concatenate
from keras.layers import Dense, Lambda, ELU, MaxPooling2D
from keras.layers import Activation, Dropout, Flatten, Dense, merge, core
from keras.layers.normalization import BatchNormalization
from keras.layers.merge import Add, Concatenate
from keras.regularizers import l2
import tensorflow as tf
from loss_functions import *
from keras import losses

from utils.BilinearUpSampling import BilinearUpSampling2D
from utils.resnet_helpers import conv_block, identity_block, atrous_conv_block, atrous_identity_block

def FCNN(opt):
    """Create neural network model, defining layer architecture."""
    model = Sequential()
    
    # Conv2D(output_depth, convolution height, convolution_width, ...)
    #5x5 trains in 1.5 times duration of 3x3
    #double layer count is linear increase in training time. about 2x
    c = 3
    act = 'relu'
    num_conv = 32
    drop = 0.2

    num_classes = opt['nb_classes']
    input = Input(shape=opt['input_shape'])

    x = Conv2D(num_conv, (c, c), padding='same')(input)
    x = BatchNormalization()(x)

    N = 2

    for i in range(N):
        x = Activation(act)(x)
        x = Dropout(drop)(x)
        x = Conv2D(num_conv, (c, c), padding='same')(x)
        x = BatchNormalization()(x)
        
    output = Conv2D(num_classes, (1, 1), padding='same', activation='softmax')(x)

    model = Model(inputs=input, outputs=output)

    model.compile(optimizer='rmsprop',
                loss=losses.categorical_crossentropy)
                #loss=weighted_binary_crossentropy(opt['presence_weight']),
                #metrics=['binary_accuracy', 'binary_crossentropy'])

    return model

def FCNN_w_skip(opt):
    from keras import backend as K
    """Create neural network model, defining layer architecture."""
    c = 3
    act = 'relu'
    num_conv = 32
    drop = 0.2

    num_classes = opt['nb_classes']
    input_shape = opt['input_shape']
    input = Input(shape=input_shape)

    x = Conv2D(num_conv, (c, c), padding='same')(input)
    x = BatchNormalization()(x)


    N = 6
    #ref: https://keunwoochoi.wordpress.com/2016/03/09/residual-networks-implementation-on-keras/
    for i in range(N):
        if i % 2 == 0:
            y = x
        x = Activation(act)(x)
        x = Dropout(drop)(x)
        
        if i % 2 == 0:
            c = 1
        else:
            c = 3

        mult = (i // 2) + 1

        x = Conv2D(num_conv * mult, (c, c), padding='same')(x)
        x = BatchNormalization()(x)
        
        if i % 2 == 1:
            x = Conv2D(num_conv, (c, c), padding='same', activation='relu')(x)
            x = Add()([x, y])
      
    output = Conv2D(num_classes, (1, 1), padding='same', activation='softmax')(x)
    model = Model(inputs=input, outputs=output)

    model.compile(optimizer='rmsprop',
                #loss=losses.categorical_crossentropy)
                loss=weighted_binary_crossentropy(opt['presence_weight']),
                metrics=['binary_accuracy', 'binary_crossentropy'])

    return model

def AtrousFCN_Resnet50_16s(opt):
    img_input = Input(shape=opt['input_shape'])
    batch_momentum=0.9
    weight_decay=0.
    image_size = opt['input_shape']
    classes = opt['nb_classes']

    bn_axis = 3
    x = img_input

    x = Conv2D(64, (7, 7), strides=(2, 2), padding='same', name='conv1', kernel_regularizer=l2(weight_decay))(x)
    x = BatchNormalization(axis=bn_axis, name='bn_conv1', momentum=batch_momentum)(x)
    x = Activation('relu')(x)
    x = MaxPooling2D((3, 3), strides=(2, 2))(x)

    x = conv_block(3, [64, 64, 256], stage=2, block='a', weight_decay=weight_decay, strides=(1, 1), batch_momentum=batch_momentum)(x)
    x = identity_block(3, [64, 64, 256], stage=2, block='b', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [64, 64, 256], stage=2, block='c', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)

    x = conv_block(3, [128, 128, 512], stage=3, block='a', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [128, 128, 512], stage=3, block='b', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [128, 128, 512], stage=3, block='c', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [128, 128, 512], stage=3, block='d', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    
    x = conv_block(3, [256, 256, 1024], stage=4, block='a', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [256, 256, 1024], stage=4, block='b', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [256, 256, 1024], stage=4, block='c', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [256, 256, 1024], stage=4, block='d', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [256, 256, 1024], stage=4, block='e', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)
    x = identity_block(3, [256, 256, 1024], stage=4, block='f', weight_decay=weight_decay, batch_momentum=batch_momentum)(x)

    x = atrous_conv_block(3, [512, 512, 2048], stage=5, block='a', weight_decay=weight_decay, atrous_rate=(2, 2), batch_momentum=batch_momentum)(x)
    x = atrous_identity_block(3, [512, 512, 2048], stage=5, block='b', weight_decay=weight_decay, atrous_rate=(2, 2), batch_momentum=batch_momentum)(x)
    x = atrous_identity_block(3, [512, 512, 2048], stage=5, block='c', weight_decay=weight_decay, atrous_rate=(2, 2), batch_momentum=batch_momentum)(x)
    
    #classifying layer
    #x = Conv2D(classes, (3, 3), dilation_rate=(2, 2), kernel_initializer='normal', activation='linear', padding='same', strides=(1, 1), kernel_regularizer=l2(weight_decay))(x)
    x = Conv2D(classes, (1, 1), kernel_initializer='he_normal', activation='linear', padding='same', strides=(1, 1), kernel_regularizer=l2(weight_decay))(x)
    x = BilinearUpSampling2D(target_size=image_size)(x)

    model = Model(img_input, x)
    
    model.compile(optimizer='adam',
                loss=binary_crossentropy_with_logits,
                metrics=['binary_accuracy', 'binary_crossentropy'])

    return model

def create_model(opt):
    #return AtrousFCN_Resnet50_16s(opt)
    #return FCNN(opt)
    return FCNN_w_skip(opt)
