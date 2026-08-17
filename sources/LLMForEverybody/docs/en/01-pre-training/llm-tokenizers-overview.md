# A Broad Overview of Tokenizers for LLMs

## 1. Three Common Tokenization Methods

You probably already know that the input and output unit of an LLM is a token, not a word or a letter. In Chinese, it is not exactly a word or a character either. But what is a token?

> We often use the word token directly. In some texts it may be translated as "token" or "label." If "label" appears below, it means token.

A token is the result of splitting text with a Tokenizer. A Tokenizer is the tool that splits text into tokens.

In LLMs, Tokenizers usually use three common splitting methods: word level, character level, and subword level. I will explain them from the perspective of two languages: English and Chinese.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（一）/1.png)

### 1.1. Word Level

#### English

Word-level tokenization is the simplest method: split text into words by spaces or punctuation.

For example, take this sentence:

>Let's do some NLP tasks.

If we split by spaces, we get these tokens:

>Let's, do, some, NLP, tasks.

If we split by punctuation, we get:

>Let, ', s, do, some, NLP, tasks, .

#### Chinese

In Chinese, tokenization is more complex. Chinese has no spaces, so splitting text into words is much harder than in English. Consider this example:

>我们来做一个自然语言处理任务。

One possible tokenization result is:

>我们，来，做，一个，自然语言处理，任务。

The advantage of this method is that it is simple and easy to understand. The downside is that it handles unknown words poorly, also called Out-of-Vocabulary or OOV. The familiar `jieba` library is based on this general approach.

> `jieba` uses statistical and rule-based methods, combining TF-IDF, TextRank, and other techniques. It builds a word graph based on a prefix dictionary and uses dynamic programming to find the maximum-probability path, which gives the segmentation result. For unknown words, `jieba` uses an HMM, a hidden Markov model, based on the ability of Chinese characters to form words, and uses the Viterbi algorithm for recognition and segmentation.

### 1.2. Character Level

#### English

Character level splits text into tokens at the letter level. This approach has a few advantages:

- the vocabulary becomes much smaller;
- OOV becomes much less of a problem, because any word can be built from characters.

For example, take this sentence:

>Let's do some NLP tasks.

After character-level splitting, we get:

>L, e, t, ', s, d, o, s, o, m, e, N, L, P, t, a, s, k, s, .

#### Chinese

In Chinese, character level means splitting text into tokens at the Chinese-character level.

For example, take this sentence:

>我们来做一个自然语言处理任务。

After splitting by character, we get:

>我，们，来，做，一，个，自，然，语，言，处，理，任，务，。

This method is not perfect either. Intuitively, working with characters instead of words is not always meaningful. In English, a single letter usually carries little meaning by itself, while the word carries the meaning. In Chinese, each character contains more information than a letter in Latin-based languages.

Also, the model ends up processing many more tokens. With word-level tokenization, a word may be one token. With character-level tokenization, the same word can easily become 10 or more tokens.

### 1.3. Subword Level

In practice, both character-level and word-level tokenization have shortcomings. Subword level sits between the two.

> Sub-word is often translated as "subword."

Subword tokenization algorithms follow this principle: frequent words should not be split into smaller subwords, while rare words should be broken into meaningful subwords.

#### English

Consider this example:

> Let's do Sub-word level tokenizer.

Tokenization result:

> let's</ w>, do</ w>, Sub, -word</ w>, level</ w>, token, izer</ w>, .</ w>,

`</ w>` usually marks the end of a word. The letter "w" is used because it is the first letter of "word"; this is a common naming convention. The exact marker may differ across implementations or tokenization methods.

#### Chinese

In Chinese, it may seem that there is no concept of subword: the smallest unit appears to be the character. So how can we use subword tokenization? Maybe through components and radicals? Do not rush. We will discuss that later.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（一）/0.png)

## 2. BPE (Byte-Pair Encoding)

Byte-Pair Encoding (BPE) was originally developed as a text compression algorithm. Philip Gage first proposed it in 1994 in the article `A New Algorithm for Data Compression`. Later, OpenAI used BPE as the Tokenizer foundation when pretraining GPT models. This approach is used in many Transformer models, including GPT, GPT-2, RoBERTa, BART, and DeBERTa.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（二）/0.png)

In this article, I will try to explain BPE as intuitively as possible, using language and examples.

This part looks at tokenization for English text. Tokenization for Chinese will be discussed later.

### 2.1. Intuitive Understanding

Assume we have a corpus containing these words:

```plaintext
faster</ w>: 8, higher</ w>:6, stronger</ w>:7
```

The number shows how many times the word appears in the corpus.

> Note: `</ w>` marks the end of a word. The letter "w" is used because it is the first letter of "word"; this is a common naming convention. The exact token may differ across implementations or tokenization methods.

**First**, we treat every character as a separate token:

```plaintext
f a s t e r</ w>: 8, h i g h e r</ w>: 6, s t r o n g e r</ w>: 7
```

The corresponding vocabulary is:

```plaintext
'a', 'e', 'f', 'g', 'h', 'i', 'n', 'o', 'r', 's', 't', 'r</ w>'
```

**Second**, we count how often each adjacent token pair appears in the corpus:

```plaintext
'fa':8,'as':8,'st':15,'te':8,'er</ w>':21,'hi':6,'ig':6,'gh':6,'he':6,'tr':7,'ro':7,'on':7,'ng':7,'ge':7
```

We merge the most frequent pair, `'e'` and `'r</ w>'`, into `'er</ w>'`. This is where the name byte pair comes from. The tokens become:

```plaintext
f a s t er</ w>: 8, h i g h er</ w>: 6, s t r o n g er</ w>: 7
```

The vocabulary changes to:

```plaintext
'a', 'f', 'g', 'h', 'i', 'n', 'o', 's','r', 't', 'er</ w>'
```

> Important: at this step, `'e'` and `'r</ w>'` were absorbed into `'er'`, because they no longer appear separately anywhere in the tokens except inside `'er'`.

**Third**, `'er</ w>'` is now its own token. We count adjacent token pair frequencies again:

```plaintext
'fa':8,'as':8,'st':15,'ter</ w>':8,'hi':6,'ig':6,'gh':6,'her</ w>':6,'tr':7,'ro':7,'on':7,'ng':7,'ger</ w>':7
```

We merge the most frequent pair, `'t'` and `'er</ w>'`, into `'ter</ w>'`. The tokens become:

```plaintext
f a s ter</ w>: 8, h i g h er</ w>: 6, s t r o n g er</ w>: 7
```

The vocabulary changes to:

```plaintext
'a', 'f', 'g', 'h', 'i', 'n', 'o', 's','r', 't', 'er</ w>', 'ter</ w>'
```

> Important: here `'er</ w>'` and `'t'` were not fully absorbed into `'ter</ w>'`, because both still appear elsewhere in the tokenized corpus.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（二）/1.png)

**Repeat these steps** until reaching the target number of tokens or target number of iterations.

These two values are the hyperparameters of the BPE algorithm and can be adjusted for the specific task.

After understanding BPE, we can look at WordPiece and SentencePiece.

## 3. WordPiece

WordPiece is a tokenization algorithm developed by Google for pretraining BERT. It was later reused in many BERT-based Transformer models, such as DistilBERT, MobileBERT, Funnel Transformers, and MPNET. Its training process is similar to BPE, but the actual tokenization method is different.

![alt text](../../../01-第一章-预训练/assest/搞懂大模型的分词器（三）/1.png)

The name WordPiece points to its core function: breaking a word into pieces. It describes the basic operation directly.

The workflow of a WordPiece tokenizer is very similar to BPE. The difference is how it chooses which token pair to merge.

WordPiece scores each candidate pair using:

```plaintext
score = freq_of_pair / (freq_of_first_element * freq_of_second_element)
```

You may also see the formula written with `log`; that turns division into subtraction and makes computation easier.

## References

See the individual tokenizer articles in this chapter for the detailed references.
