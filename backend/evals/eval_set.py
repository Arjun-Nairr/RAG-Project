# Fixed retrieval eval set - one question per row, tagged with which paper
# actually contains the answer. Reused across pipeline configs (chunk size,
# top-K, etc.) so comparisons are apples-to-apples: same questions, same
# ground truth, only the pipeline changes.

EVAL_QUESTIONS = [
    {"question": "What is multi-head attention?", "expected_source": "attention_is_all_you_need.pdf"},
    {"question": "What is scaled dot-product attention?", "expected_source": "attention_is_all_you_need.pdf"},
    {"question": "How does positional encoding work in the Transformer?", "expected_source": "attention_is_all_you_need.pdf"},
    {"question": "What is the BERT pretraining objective?", "expected_source": "bert.pdf"},
    {"question": "What is masked language modeling?", "expected_source": "bert.pdf"},
    {"question": "How does BERT differ from GPT in terms of bidirectionality?", "expected_source": "bert.pdf"},
    {"question": "How does LoRA reduce the number of trainable parameters?", "expected_source": "lora.pdf"},
    {"question": "What is low-rank decomposition in LoRA?", "expected_source": "lora.pdf"},
    {"question": "Which weight matrices does LoRA typically apply to?", "expected_source": "lora.pdf"},
    {"question": "What is the difference between RAG-Sequence and RAG-Token models?", "expected_source": "rag_paper.pdf"},
    {"question": "How does retrieval-augmented generation combine parametric and non-parametric memory?", "expected_source": "rag_paper.pdf"},
    {"question": "What retriever is used in the RAG paper?", "expected_source": "rag_paper.pdf"},
    {"question": "What is few-shot learning in the context of GPT-3?", "expected_source": "gpt3_few_shot.pdf"},
    {"question": "How many parameters does GPT-3 have?", "expected_source": "gpt3_few_shot.pdf"},
    {"question": "What is in-context learning?", "expected_source": "gpt3_few_shot.pdf"},
    # slightly harder, paraphrased the way a student would actually ask while
    # studying - not the paper's exact terminology, still a real question
    # a real student would type
    {"question": "Why did the Transformer get rid of recurrence?", "expected_source": "attention_is_all_you_need.pdf"},
    {"question": "How does the model know word order without RNNs?", "expected_source": "attention_is_all_you_need.pdf"},
    {"question": "Why can BERT use context from both directions instead of just left to right?", "expected_source": "bert.pdf"},
    {"question": "What's the next sentence prediction task about?", "expected_source": "bert.pdf"},
    {"question": "Why is LoRA cheaper to train than fully fine-tuning a model?", "expected_source": "lora.pdf"},
    {"question": "What happens to the original model weights when you use LoRA?", "expected_source": "lora.pdf"},
    {"question": "Why combine a language model with a retriever instead of just using the language model alone?", "expected_source": "rag_paper.pdf"},
    {"question": "Can RAG update its knowledge without retraining the whole model?", "expected_source": "rag_paper.pdf"},
    {"question": "Does GPT-3 need to be retrained to learn a new task?", "expected_source": "gpt3_few_shot.pdf"},
    {"question": "What's the difference between few-shot and zero-shot for GPT-3?", "expected_source": "gpt3_few_shot.pdf"},
]
