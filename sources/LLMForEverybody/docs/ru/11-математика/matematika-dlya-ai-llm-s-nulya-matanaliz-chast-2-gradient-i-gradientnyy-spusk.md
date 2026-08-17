Математика для AI/LLM с нуля: математический анализ, часть 2, gradient и gradient descent

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Когда речь заходит о математике, нужной для AI, кто-то вспоминает университетский страх перед высшей математикой или думает, не придется ли снова доставать оба тома курса высшей математики.

На самом деле базовые знания высшей математики, нужные для AI, - это прежде всего calculus, главным образом ради gradient descent и backpropagation. Эти знания несложные: если понять базовые понятия calculus, дальше все можно разобрать.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание calculus.

- Хотя мы говорим о calculus, в математике для AI самое важное - differentiation, а если точнее, differential coefficient, то есть derivative.

## 2. Partial derivative

В functions of several variables, если derivative берется только по одной переменной, а остальные переменные считаются constants, такая derivative называется partial derivative.

Метод вычисления partial derivative похож на обычную derivative, нужно только помнить, что остальные переменные считаются constants.

Partial derivative обычно обозначают символом $\partial$. Например, partial derivative функции $f(x, y)$ по $x$ записывается как $\frac{\partial f}{\partial x}$, а по $y$ - как $\frac{\partial f}{\partial y}$.

![alt text](../../../11-第十一章-数学/calculus/assest/3.png)

## 3. Gradient


***Slope***

В функции одной переменной есть понятие slope: оно показывает rate of change функции в конкретной точке.

![alt text](../../../11-第十一章-数学/calculus/assest/5.png)

***Gradient***

В функции нескольких переменных есть понятие gradient: оно показывает rate of change функции в конкретной точке.

![alt text](../../../11-第十一章-数学/calculus/assest/4.png)

## 4. Gradient descent

Gradient descent - optimization algorithm для минимизации значения функции.

Gradient Descent - iterative optimization algorithm для поиска local minimum функции. В machine learning и deep learning он часто используется для минимизации loss function, чтобы найти оптимальные значения параметров модели. Основные шаги и понятия gradient descent:

1. **Objective function**: сначала нужна objective function, обычно loss function, зависящая от параметров модели. Цель - найти значения параметров, при которых эта функция минимальна.

2. **Gradient**: gradient - это vector, составленный из partial derivatives objective function по каждому параметру. Gradient указывает направление самого быстрого роста функции.

3. **Direction of descent**: чтобы минимизировать функцию, нужно обновлять параметры в направлении, противоположном gradient, то есть в направлении steepest descent.

4. **Learning rate**: learning rate - положительный scalar, определяющий step size движения в направлении gradient descent. Если learning rate слишком большой, можно перескочить minimum или даже разойтись; если слишком маленький, convergence будет очень медленной.

5. **Iterative update**: на каждой iteration алгоритм вычисляет gradient текущих параметров и обновляет параметры, двигая их в направлении gradient descent. Процесс повторяется до выполнения stopping condition: например, gradient достаточно мал, достигнуто заданное число iterations или изменение objective function ниже некоторого threshold.

6. **Stopping condition**: gradient descent algorithm требует condition, определяющее, когда остановить iterations. Частые conditions: norm of gradient меньше очень маленького положительного числа, достигнуто max iterations или improvement objective function ниже threshold.

Простая update formula для gradient descent:

$\theta_{\text{new}} = \theta_{\text{old}} - \alpha \nabla_\theta J(\theta_{\text{old}})$

Здесь $\theta$ означает model parameters, $\alpha$ - learning rate, а $\nabla_\theta J(\theta)$ - gradient objective function $J$ по parameters $\theta$.

Optimization algorithms, которые сейчас используются в deep learning, см. в предыдущей статье.

## 5. Second derivative

Интуитивно: second derivative - это derivative of derivative, то есть rate of change от rate of change функции.

В function of one variable second derivative показывает curvature функции: положительное значение означает, что функция concave up, отрицательное - concave down.

![alt text](../../../11-第十一章-数学/calculus/assest/6.png)

В functions of several variables second derivative показывает curvature функции в конкретной точке, а Hessian matrix является matrix form second derivatives.

![alt text](../../../11-第十一章-数学/calculus/assest/7.png)

## 6. Hessian matrix

Для примера на рисунке ниже можно вычислить second derivative для каждой partial derivative.

![alt text](../../../11-第十一章-数学/calculus/assest/8.png)

Даем notation definition second derivative:

![alt text](../../../11-第十一章-数学/calculus/assest/9.png)

Даем definition Hessian matrix:

![alt text](../../../11-第十一章-数学/calculus/assest/10.png)

Итак, форма second derivative выглядит так:

![alt text](../../../11-第十一章-数学/calculus/assest/11.png)

### 7. Итоги по calculus

Высшая математика занимает большую часть университетской математики, но в AI нужные знания высшей математики в основном сосредоточены именно в calculus, главным образом ради gradient descent и backpropagation. Эту работу фреймворки вроде PyTorch или TensorFlow уже сделали за нас: нужно только вызывать соответствующие functions.

## Ссылки

<div id="refer-anchor-1"></div>

[1] [machine-learning-calculus](https://www.coursera.org/learn/machine-learning-calculus/home/module/2)

## Подписывайтесь на мой GitHub и WeChat Official Account [Настоящий корабль Тесея]. Некогда объяснять, все на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Все полностью open source, буду рад вашим Star и Fork!
