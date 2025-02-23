mkdir saved_models
python run_codebert.py \
    --output_dir=saved_models \
    --config_name=microsoft/codebert-base \
    --model_name_or_path=microsoft/codebert-base \
    --tokenizer_name=microsoft/codebert-base \
    --do_train \
    --train_data_file=dataset/dataset/train.txt \
    --eval_data_file=dataset/dataset/valid.txt \
    --test_data_file=dataset/dataset/test.txt \
    --epoch 10 \
    --code_length 512 \
    --data_flow_length 128 \
    --train_batch_size 32 \
    --eval_batch_size 32 \
    --learning_rate 2e-5 \
    --max_grad_norm 1.0 \
    --evaluate_during_training \
    --seed 123456 2>&1| tee saved_models/cb-train.log