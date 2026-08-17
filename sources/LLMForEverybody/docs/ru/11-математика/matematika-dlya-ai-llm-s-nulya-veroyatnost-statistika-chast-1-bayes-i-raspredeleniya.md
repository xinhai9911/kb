Математика для AI/LLM с нуля: вероятность и статистика, часть 1, Bayes' theorem и probability distributions

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Probability and statistics - одна из базовых математических областей для AI. Владение probability and statistics критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по probability and statistics, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание probability and statistics.

- Probability - математический инструмент для описания возможности random phenomena; это mathematical model, описывающая степень uncertainty.
- Statistics - наука о сборе, обработке, анализе и интерпретации данных; это метод изучения данных для извлечения information.

## 1. Bayes

### 1.1. Интуитивное понимание Bayes' theorem

Каждый день хочется умереть, но медосмотр должен быть чистым!

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/0.png)

Что вы подумаете, если увидите в медицинском отчете, что у вас обнаружено некоторое заболевание?

Предположим, incidence rate заболевания равен 1 к 10 000, а test accuracy медицинского центра равна 99%. Вопрос: если отчет показывает, что у вас есть это заболевание, какова probability, что вы действительно больны?

***Подумайте: что подсказывает intuition? Probability высокая или низкая?***

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/1.png)

Можно рассуждать так:

1. Среди 1 000 000 человек 100 больны, 999 900 не больны;
2. Из 100 больных 99 получат positive result, 1 не будет найден;
3. Из 999 900 здоровых 9 999 получат positive result, 989 901 не получит.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/2.png)

Значит, если ваш отчет показывает это заболевание, probability того, что вы действительно больны:

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/3.png)

Совпало с вашей intuition?

### 1.2. Prior and Posterior Probability

Prior Probability: initial judgment о probability события до учета новых evidence.

В этом сценарии это probability того, что человек болен: P(sick) = 0.0001

Posterior Probability: revised judgment о probability события после учета новых evidence.

В этом сценарии это probability того, что человек действительно болен, если медицинский отчет показывает болезнь: P(sick|diagnosed sick) = 0.0098

### 1.3. Bayes' Theorem

Запишем задачу **incidence rate заболевания равен 1 к 10 000, а test accuracy медицинского центра равна 99%** в математической форме:

$$P(sick) = 0.0001$$

$$P(not\ sick) = 0.9999$$

$$P(diagnosed\ sick|sick) = 0.99$$

$$P(diagnosed\ sick|not sick) = 0.01$$

Наша цель:

$$P(sick|diagnosed\ sick)$$

Bayes' Theorem:

$$P(sick|diagnosed\ sick) = \frac{P(diagnosed\ sick|sick)P(sick)}{P(diagnosed\ sick)}$$

Проблема в том, что мы не знаем $P(diagnosed\ sick)$, но можем найти его через Total Probability Theorem:

$$P(diagnosed\ sick) = P(diagnosed\ sick|sick)P(sick) + P(diagnosed\ sick|not\ sick)P(not\ sick)$$

Следовательно:

$$P(sick|diagnosed\ sick) = \frac{P(diagnosed\ sick|sick)P(sick)}{P(diagnosed\ sick|sick)P(sick) + P(diagnosed\ sick|not\ sick)P(not\ sick)}$$

Подставляем numbers:

$$P(sick|diagnosed\ sick) = \frac{0.99*0.0001}{0.99*0.0001 + 0.01*0.9999} = 0.0098$$

Итак, если ваш отчет показывает это заболевание, probability того, что вы действительно больны, равна 0.0098, то есть меньше 1%.

### 1.4. Naive Bayes

Важное применение Bayes' theorem - Naive Bayes Classifier.

Naive Bayes Classifier - простой probabilistic classifier на базе Bayes' theorem. Он предполагает, что features независимы друг от друга.

- Часть родившихся в 80-х/90-х наверняка помнит выражения вроде "interesting" и "too young too simple"; молодым людям не стоит быть слишком naive!

Naive Bayes называется naive, потому что предполагает independence features. Это assumption часто не выполняется в реальных приложениях, но Naive Bayes Classifier на практике работает хорошо.

## 2. Discrete Probability Distribution

### 2.1. Binomial Distribution

Binomial distribution - discrete probability distribution в statistics. Оно описывает probability distribution числа successes в fixed number independent experiments, где у каждого experiment только два possible outcomes, success или failure, и probability success одинакова.

Formula binomial distribution:

$P(X = k) = \binom{n}{k} p^k (1-p)^{n-k}$

Где:
- $n$ - total number experiments.
- $k$ - number successes.
- $p$ - probability success в каждом experiment.
- $\binom{n}{k}$ - combination number, number ways выбрать $k$ successes из $n$ experiments; formula $\binom{n}{k} = \frac{n!}{k!(n-k)!}$.

Expected value $E(X)$ и variance $Var(X)$ binomial distribution:

$E(X) = np$
$Var(X) = np(1-p)$

Graph binomial distribution - discrete, asymmetric distribution; при $p = 0.5$ distribution symmetric. Когда $n$ large, binomial distribution можно approximate normal distribution.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/4.png)

### 2.2. Bernoulli Distribution

Bernoulli distribution - special case binomial distribution: когда $n = 1$, binomial distribution становится Bernoulli distribution.

Formula Bernoulli distribution:

$P(X = k) = p^k (1-p)^{1-k}$

Где:

- $k = 0$ или $k = 1$.

Expected value $E(X)$ и variance $Var(X)$ Bernoulli distribution:

$E(X) = p$

$Var(X) = p(1-p)$

- Имя Bernoulli встречается в разных областях, например Bernoulli's law в fluid mechanics. Все ли это сделал один человек? На самом деле это представители family Bernoulli: они родственники, но не один и тот же человек. Bernoulli distribution предложил швейцарский математик Jacob Bernoulli. Его младший брат Johann Bernoulli тоже был известным математиком и учителем Euler. Bernoulli's law в fluid mechanics предложил Daniel Bernoulli, сын Johann Bernoulli.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/5.webp)

## 3. Continuous Probability Distribution

### 3.1. Probability Density Function

Probability Density Function (PDF) описывает probability distribution continuous random variable. Для continuous random variable нельзя, как для discrete random variable, напрямую дать probability каждого value, потому что variable может принимать infinitely many values, а probability отдельного value обычно равна 0. Поэтому PDF описывает probability того, что continuous random variable попадет в некоторый interval.

PDF $f(x)$ имеет такие properties:

1. Non-negativity: для всех $x$, $f(x) \geq 0$;
2. Normalization: integral PDF по всей domain равен 1: $\int_{-\infty}^{\infty} f(x) \, dx = 1$;
3. Probability calculation: probability того, что continuous random variable $X$ попадает в interval $[a, b]$, задается integral PDF на этом interval: $P(a \leq X \leq b) = \int_{a}^{b} f(x) \, dx$.

### 3.2. Cumulative Distribution Function

Cumulative Distribution Function (CDF) - function, описывающая probability distribution random variable. Она дает probability того, что random variable принимает value меньше или равно некоторому value. Для любого real number $x$ CDF $F(x)$ определяется так:

$F(x) = P(X \leq x)$

Где $X$ - random variable.

CDF имеет такие properties:

1. **Non-decreasing**: $F(x)$ non-decreasing function, то есть если $x_1 < x_2$, то $F(x_1) \leq F(x_2)$;
2. **Right-continuity**: $F(x)$ right-continuous, то есть $\lim_{y \to x^+} F(y) = F(x)$;
3. **Limits**:
   - когда $x$ стремится к negative infinity, $F(x)$ стремится к 0: $\lim_{x \to -\infty} F(x) = 0$;
   - когда $x$ стремится к positive infinity, $F(x)$ стремится к 1: $\lim_{x \to \infty} F(x) = 1$.

Для discrete random variable CDF является step function: она jumps в каждом possible value random variable, а height jump равна probability этого value.

Для continuous random variable CDF continuous и может быть получена integral PDF $f(x)$:

$F(x) = \int_{-\infty}^{x} f(t) \, dt$

CDF очень важна в statistics. Она используется для вычисления probability попадания random variable в interval, а также для comparison и analysis probability distributions. Через CDF можно получить median, quantiles, expected value, variance и другие statistics random variable.

### 3.3. Uniform Distribution

Uniform Distribution - простое continuous probability distribution, у которого PDF $f(x)$ constant внутри interval и 0 вне interval. PDF uniform distribution:

$$f(x) = \begin{cases} \frac{1}{b-a}, & a \leq x \leq b \\ 0, & x < a \text{ or } x > b \end{cases}$$

### 3.4. Normal Distribution

Normal Distribution - одно из самых важных continuous probability distributions в statistics. Оно имеет много важных properties и широко применяется в natural sciences, social sciences, engineering и других областях.

PDF normal distribution $f(x)$:

$$f(x) = \frac{1}{\sqrt{2\pi}\sigma} e^{-\frac{(x-\mu)^2}{2\sigma^2}}$$

Где $\mu$ - mean, $\sigma$ - standard deviation.

Expected value $E(X)$ и variance $Var(X)$ normal distribution:

$$E(X) = \mu$$

$$Var(X) = \sigma^2$$

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/6.png)

У normal distribution есть важное property - rule 68-95-99.7: в normal distribution 68% data лежит в пределах одного standard deviation от mean, 95% - в пределах двух standard deviations, 99.7% - в пределах трех standard deviations.

- Normal distribution также называется Gaussian distribution. Оно предложено немецким математиком Gauss в XIX веке. Gauss - математик среди математиков: у него огромное количество достижений не только в mathematics, но и в physics, astronomy, statistics и других областях. Gaussian distribution - самое распространенное distribution в природе; многие natural phenomena можно описать через Gaussian distribution, например height, weight и IQ людей.

**Задумывались ли вы, почему normal distribution так часто встречается в природе?** Подписывайтесь, дальше поговорим про Central Limit Theorem.


## Ссылки

<div id="refer-anchor-1"></div>

[1] [robability-and-statistics](https://www.coursera.org/learn/machine-learning-probability-and-statistics/home/week/1)

[2] [伯努利家族](https://zh.wikipedia.org/wiki/%E4%BC%AF%E5%8A%AA%E5%88%A9%E5%AE%B6%E6%97%8F)

[3] [伯努利定律](https://zh.wikipedia.org/wiki/%E4%BC%AF%E5%8A%AA%E5%88%A9%E5%AE%9A%E5%BE%8B)

## Подписывайтесь на мой GitHub и WeChat Official Account [Настоящий корабль Тесея]. Некогда объяснять, все на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Все полностью open source, буду рад вашим Star и Fork!
