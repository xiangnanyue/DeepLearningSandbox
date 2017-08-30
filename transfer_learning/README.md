python fine-tune.py --train_dir=/tmp/kaggle_photos/raw-data/train/ --val_dir=/tmp/kaggle_photos/raw-data/validation/ --nb_epoch=2 --batch_size=32

python kaggle_fine_tune.py --train_dir=/tmp/binary_data_dir/train/ --val_dir=/tmp/binary_data_dir/validation/ --batch_size=64 --nb_epoch=5 --save_to_file --output_model_file=batch64_epoch5_transfer.model

python predict.py --image=/tmp/binary_data_dir/validation/0/2404_left.jpeg --model=./inceptionv3-ft.model

 python kaggle_fine_tune.py --train_dir=../../300/train/ --val_dir=../../300/validation/ --batch_size=64 --nb_epoch=5 --save_to_file --output_model_file=batch64_epoch5_transfer_reshape.model