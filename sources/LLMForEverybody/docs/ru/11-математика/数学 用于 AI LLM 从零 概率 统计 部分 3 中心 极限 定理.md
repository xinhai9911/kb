---
aliases: ["matematika-dlya-ai-llm-s-nulya-veroyatnost-statistika-chast-3-centralnaya-predelnaya-teorema"]
---

Математика для AI/LLM с нуля: вероятность и статистика, часть 3, Central Limit Theorem

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Probability and statistics - одна из базовых математических областей для AI. Владение probability and statistics критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по probability and statistics, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание probability and statistics.

- Probability - математический инструмент для описания возможности random phenomena; это mathematical model, описывающая степень uncertainty.
- Statistics - наука о сборе, обработке, анализе и интерпретации данных; это метод изучения данных для извлечения information.

## 1. Normal Distribution

- Normal Distribution, также Gaussian Distribution, - одно из самых важных distributions в probability and statistics и одно из самых common distributions.

Вы наверняка слышали о normal distribution и знаете, что это самое распространенное distribution в природе. Даже английское слово `Normal` указывает на обычность: height, weight, IQ людей и так далее часто следуют normal distribution.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/15.png)

Но знаете ли вы, почему height, weight, IQ и другие признаки людей следуют normal distribution? Ответ: Central Limit Theorem.

Central Limit Theorem утверждает: по мере роста числа random variables сумма многих independent and identically distributed random variables с finite variance стремится к normal distribution.

Height, weight, IQ человека и так далее определяются множеством genes. Каждый gene можно рассматривать как random variable, а сумма этих random variables дает height, weight, IQ и т. д. Согласно Central Limit Theorem, эти суммы стремятся к normal distribution.

## 2. Law of Large Numbers

Law of Large Numbers - важная theorem в probability and statistics. Она описывает явление, при котором mean sequence random variables в repeated experiments стремится к expected value.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/16.png)

Law of Large Numbers делится на Weak Law of Large Numbers и Strong Law of Large Numbers.

- Weak Law of Large Numbers: для sequence independent and identically distributed random variables mean в repeated experiments стремится к expected value with probability 1.

- Strong Law of Large Numbers: для sequence independent and identically distributed random variables mean almost surely converges к expected value.


## 3. Central Limit Theorem

### Интуитивное понимание

Интуитивное понимание Central Limit Theorem: для random variables с любым distribution, если repeated experiments достаточно много, distribution их sum будет стремиться к normal distribution.

### CLT for Discrete Random Variables

Рассмотрим coin toss. Outcome coin toss - heads или tails; heads считаем 1, значит outcome равен 0 или 1 и следует binomial distribution.

Один toss: possible outcomes 0 и 1, probabilities 0.5 и 0.5.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/17.png)

Два tosses: possible outcomes 0, 1, 2; probabilities 0.25, 0.5, 0.25.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/18.png)

Три tosses: possible outcomes 0, 1, 2, 3; probabilities 0.125, 0.375, 0.375, 0.125.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/19.png)

По мере роста number coin tosses distribution graph будет стремиться к normal distribution.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/20.png)


### CLT for Continuous Random Variables

Рассмотрим uniform distribution. Здесь пример - waiting time звонка в customer service. Предположим, duration находится между 0 и 15 minutes, значит duration follows uniform distribution.

Distribution sample одного phone call:

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/21.png)

Distribution sum waiting time двух calls:

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/22.png)

Distribution sum waiting time трех calls:

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/23.png)

По мере роста number samples distribution graph будет стремиться к normal distribution.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/24.png)

## 4. История Central Limit Theorem

У Central Limit Theorem интересная история. Первую версию theorem открыл французский математик de Moivre. В выдающейся статье 1733 года он использовал normal distribution для оценки distribution числа heads при большом количестве coin tosses. Этот опередивший время результат почти был забыт, но знаменитый французский математик Laplace спас эту малоизвестную theory в своем труде `Théorie Analytique des Probabilités`, опубликованном в 1812 году.

Laplace расширил theory de Moivre и показал, что binomial distribution можно approximate normal distribution. Но, как и открытие de Moivre, результат Laplace в то время не получил большого внимания. Только к концу XIX века важность Central Limit Theorem стала широко известна.

В 1901 году русский математик Lyapunov дал definition Central Limit Theorem для более general random variables и строго доказал ее математически. Сегодня Central Limit Theorem считается главной theorem в probability theory.


## Ссылки

<div id="refer-anchor-1"></div>

[1] [robability-and-statistics](https://www.coursera.org/learn/machine-learning-probability-and-statistics/home/week/3)

[2] [中心极限定理](https://zh.wikipedia.org/wiki/%E4%B8%AD%E5%BF%83%E6%9E%81%E9%99%90%E5%AE%9A%E7%90%86)


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：数学
