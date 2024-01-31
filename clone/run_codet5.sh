mkdir saved_models
python run_codet5.py \
    --output_dir=saved_models \
    --task=clone \
    --config_name=salesforce/codet5-base \
    --model_name_or_path=salesforce/codet5-base \
    --tokenizer_name=salesforce/codet5-base \
    --do_train \
    --train_data_file=dataset/dataset/small/train.txt \
    --eval_data_file=dataset/dataset/small/valid.txt \
    --test_data_file=dataset/dataset/small/test.txt \
    --epoch 1 \
    --code_length 512 \
    --data_flow_length 128 \
    --train_batch_size 4 \
    --eval_batch_size 4 \
    --learning_rate 2e-5 \
    --max_grad_norm 1.0 \
    --evaluate_during_training \
    --seed 123456 2>&1| tee saved_models/cb-train.log