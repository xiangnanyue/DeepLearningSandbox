import os
import sys
import glob
import argparse
import matplotlib.pyplot as plt
import gc
import numpy as np

from keras import __version__
from keras.applications.inception_v3 import InceptionV3, preprocess_input
from keras.models import Model
from keras.layers import Dense, GlobalAveragePooling2D, Dropout, Convolution2D, GlobalMaxPool2D, Flatten, Reshape
from keras.preprocessing.image import ImageDataGenerator
from keras.optimizers import SGD, Adam


IM_WIDTH, IM_HEIGHT = 299, 299 #fixed size for InceptionV3
NB_EPOCHS = 10
BAT_SIZE = 64
FC_SIZE = 20 #1024
NB_IV3_LAYERS_TO_FREEZE = 172

# 计算train和validation两个文件夹下面的文件个数
def get_nb_files(directory):
  """Get number of files by searching directory recursively"""
  if not os.path.exists(directory):
    return 0
  cnt = 0
  for r, dirs, files in os.walk(directory):
    for dr in dirs:
      cnt += len(glob.glob(os.path.join(r, dr + "/*")))
  return cnt


def setup_to_transfer_learn(model, base_model):
  """Freeze all layers and compile the model"""
  for layer in base_model.layers:
    layer.trainable = False
  #model.compile(optimizer='rmsprop', loss='categorical_crossentropy', metrics=['accuracy'])
  model.compile(optimizer=Adam(0.00005), loss='categorical_crossentropy', metrics=['accuracy'])

def add_new_last_layer(base_model, nb_classes):
  """Add last layer to the convnet

  Args:
    base_model: keras model excluding top
    nb_classes: # of classes

  Returns:
    new keras model with last layer
  """
  x = base_model.output
  print("base model output shape :",np.shape(x))
  #x = Convolution2D(32*2**1, 3, 3, activation='relu')(x)
  #print("convolution 2d shape :", np.shape(x))
  x = GlobalAveragePooling2D()(x)
  #x = Reshape((-1),input_shape=(299,299,2048))(x)

  print("after flatten output shape :", np.shape(x))
  x = Dense(FC_SIZE, activation='relu')(x) #new FC layer, random init
  x = Dropout(0.5)(x)
  x = Dense(FC_SIZE, activation="relu")(x)
  predictions = Dense(nb_classes, activation='softmax')(x) #new softmax layer
  model = Model(input=base_model.input, output=predictions)
  return model


def setup_to_finetune(model):
  """Freeze the bottom NB_IV3_LAYERS and retrain the remaining top layers.

  note: NB_IV3_LAYERS corresponds to the top 2 inception blocks in the inceptionv3 arch

  Args:
    model: keras model
  """
  for layer in model.layers[:NB_IV3_LAYERS_TO_FREEZE]:
     layer.trainable = False
  for layer in model.layers[NB_IV3_LAYERS_TO_FREEZE:]:
     layer.trainable = True
  model.compile(optimizer=SGD(lr=0.00005, momentum=0.9), loss='categorical_crossentropy', metrics=['accuracy'])


def train(args):
  print("args: fine_tune", args.fine_tune)
  print("args: output_model_file", args.output_model_file)

  """Use transfer learning and fine-tuning to train a network on a new dataset"""
  nb_train_samples = get_nb_files(args.train_dir)
  nb_classes = len(glob.glob(args.train_dir + "/*"))
  nb_val_samples = get_nb_files(args.val_dir)
  nb_epoch = int(args.nb_epoch)
  batch_size = int(args.batch_size)

  # data prep
  train_datagen =  ImageDataGenerator(
      preprocessing_function=preprocess_input,
      rotation_range=30,
      width_shift_range=0.2,
      height_shift_range=0.2,
      shear_range=0.2,
      zoom_range=0.2,
      horizontal_flip=True
  )
  test_datagen = ImageDataGenerator(
      preprocessing_function=preprocess_input,
      rotation_range=30,
      width_shift_range=0.2,
      height_shift_range=0.2,
      shear_range=0.2,
      zoom_range=0.2,
      horizontal_flip=True
  )

  train_generator = train_datagen.flow_from_directory(
    args.train_dir,
    target_size=(IM_WIDTH, IM_HEIGHT),
    batch_size=batch_size,
  )

  validation_generator = test_datagen.flow_from_directory(
    args.val_dir,
    target_size=(IM_WIDTH, IM_HEIGHT),
    batch_size=batch_size,
  )

  # setup model
  base_model = InceptionV3(weights='imagenet', include_top=False) #include_top=False excludes final FC layer
  model = add_new_last_layer(base_model, nb_classes)

  # transfer learning
  setup_to_transfer_learn(model, base_model)

  '''self, generator,
      steps_per_epoch,
      epochs=1,
      verbose=1,
      callbacks=None,
      validation_data=None,
      validation_steps=None,
      class_weight=None,
      max_queue_size=10,
      workers=1,
      use_multiprocessing=False,
      shuffle=True,
      initial_epoch=0
  '''
  steps = int(nb_train_samples/batch_size)
  #steps = 10
  val_steps = nb_val_samples/2
  #val_steps = 1
  history_tl = model.fit_generator(
    train_generator,
    steps_per_epoch=steps,
    epochs=nb_epoch,
    validation_data=validation_generator,
    validation_steps=val_steps,
    class_weight='auto')

  # fine-tuning, first try without this fine-tuning
  if args.fine_tune:
    print("set up fine-tune")
    setup_to_finetune(model)

    #print("start evaluation generator...")
    history_ft = model.fit_generator(
        train_generator,
        steps_per_epoch=steps,
        epochs=nb_epoch,
        validation_data=validation_generator,
        validation_steps=val_steps,
        class_weight='auto')
    print("fine-tune finished!")

  if args.save_to_file:
    print("save to file...")
    model.save(args.output_model_file)
    print("file saved to", args.output_model_file)

  if args.plot and args.fine_tune:
    plot_training(history_ft)


def plot_training(history):
  acc = history.history['acc']
  val_acc = history.history['val_acc']
  loss = history.history['loss']
  val_loss = history.history['val_loss']
  epochs = range(len(acc))

  plt.plot(epochs, acc, 'r.')
  plt.plot(epochs, val_acc, 'r')
  plt.title('Training and validation accuracy')

  plt.figure()
  plt.plot(epochs, loss, 'r.')
  plt.plot(epochs, val_loss, 'r-')
  plt.title('Training and validation loss')
  plt.show()

def restore_training(base_model, nb_classes, check_file):
  #Saved models can be reinstantiated via `keras.models.load_model`
  container = add_new_last_layer(base_model, nb_classes)
  model = Model.load_weights(container, check_file)

  return model


if __name__=="__main__":
  a = argparse.ArgumentParser()
  a.add_argument("--train_dir")
  a.add_argument("--val_dir")
  a.add_argument("--nb_epoch", default=NB_EPOCHS)
  a.add_argument("--batch_size", default=BAT_SIZE)
  a.add_argument("--output_model_file", default="inceptionv3-ft.model")
  a.add_argument("--fine_tune", action="store_true")
  a.add_argument("--save_to_file", action="store_true")
  a.add_argument("--plot", action="store_true")

  args = a.parse_args()
  if args.train_dir is None or args.val_dir is None:
    a.print_help()
    sys.exit(1)

  if (not os.path.exists(args.train_dir)) or (not os.path.exists(args.val_dir)):
    print("directories do not exist")
    sys.exit(1)

  train(args)
  gc.collect()

