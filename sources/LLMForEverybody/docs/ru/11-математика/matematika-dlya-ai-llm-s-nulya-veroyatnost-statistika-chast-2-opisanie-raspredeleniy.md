Математика для AI/LLM с нуля: вероятность и статистика, часть 2, способы описания distributions

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Probability and statistics - одна из базовых математических областей для AI. Владение probability and statistics критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по probability and statistics, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание probability and statistics.

- Probability - математический инструмент для описания возможности random phenomena; это mathematical model, описывающая степень uncertainty.
- Statistics - наука о сборе, обработке, анализе и интерпретации данных; это метод изучения данных для извлечения information.

## 1. Expectation and Variance

Expected Value и Variance - два базовых понятия probability theory и statistics. Они описывают соответственно ***central tendency*** и ***dispersion*** random variable.

### Expected Value

Expected value - mean или long-term average random variable. Для discrete random variable $X$ expected value $E(X)$ определяется так:
$E(X) = \sum_{i} x_i \cdot P(x_i)$
где $x_i$ - все possible values random variable $X$, а $P(x_i)$ - probability того, что $X$ принимает value $x_i$.

Для continuous random variable $X$ expected value $E(X)$ определяется так:
$E(X) = \int_{-\infty}^{\infty} x \cdot f(x) \, dx$
где $f(x)$ - probability density function $X$.

### Variance

Variance - metric dispersion random variable. Она описывает степень отклонения values random variable от expected value. Для discrete random variable $X$ variance $Var(X)$:
$Var(X) = E[(X - E(X))^2] = \sum_{i} (x_i - E(X))^2 \cdot P(x_i)$

Для continuous random variable $X$ variance $Var(X)$:
$Var(X) = E[(X - E(X))^2] = \int_{-\infty}^{\infty} (x - E(X))^2 \cdot f(x) \, dx$

Square root variance называется Standard Deviation. Она имеет те же units, что и исходная random variable, поэтому в практике более интуитивна.

### Properties expectation и variance

1. Linearity expectation: для любых constants $a$ и $b$, а также random variables $X$ и $Y$:
   $E(aX + bY) = aE(X) + bE(Y)$

2. Properties variance: для любых constants $a$ и $b$, а также random variable $X$:
   $Var(aX + b) = a^2 Var(X)$
   Обратите внимание: constant $b$ не влияет на variance, потому что variance описывает dispersion и не зависит от location.

## 2. Skewness and Kurtosis

Expected value и variance - два basic statistics для описания central tendency и dispersion random variable distribution. Expected Value дает average random variable, а Variance описывает deviation values random variable от expected value. Хотя эти две statistics дают важную information о distribution, их недостаточно, чтобы полно описать все features distribution. Поэтому нужны Skewness и Kurtosis.

### Skewness

Skewness - statistic, описывающая asymmetry distribution. Она измеряет degree of skew, то есть с какой стороны tail distribution длиннее или короче. Если distribution symmetric, skewness равна 0. Если right side (positive side) длиннее left side, skewness positive; это right-skewed или positive skew. Если left side длиннее right side, skewness negative; это left-skewed или negative skew. Formula:
$Skewness = \frac{E[(X - \mu)^3]}{\sigma^3}$
где $\mu$ - mean, $\sigma$ - standard deviation.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/7.png)

### Kurtosis

Kurtosis - statistic, описывающая "peakedness" или "flatness" distribution. Она измеряет sharpness top distribution и thickness tails. Kurtosis сравнивается с normal distribution, у которой kurtosis равна 0. Если kurtosis distribution больше 0, оно sharper than normal distribution; если меньше 0, оно flatter than normal distribution. Formula:
$Kurtosis = \frac{E[(X - \mu)^4]}{\sigma^4} - 3$
где $\mu$ - mean, $\sigma$ - standard deviation.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/8.png)

### Зачем нужны skewness и kurtosis

1. **Более полное описание distribution**: expected value и variance описывают только center и dispersion, а skewness и kurtosis добавляют information о shape distribution, позволяя лучше понять data.
2. **Выявление abnormal distributions**: skewness и kurtosis помогают находить distributions, не соответствующие normality assumption, что важно для многих statistical analyses и model building.
3. **Risk management**: в finance и других областях skewness и kurtosis важны для risk assessment, потому что дают information о possibility extreme values, что критично для portfolio management и risk control.

Итак, skewness и kurtosis - важное дополнение к описанию features random variable distribution. Вместе с expected value и variance они дают более полную картину distribution.

## 3. Quantile and Boxplot

### 3.1. Quantile

Quantile - value в statistics, описывающее distribution data. Оно делит dataset на continuous intervals с одинаковой probability. Quantile помогает измерять relative position data, а также shape и dispersion distribution.

### Definition

Для random variable $X$ и заданной probability $p$ (где $0 < p < 1$), quantile $Q(p)$ - value, удовлетворяющее:

$P(X \leq Q(p)) = p$

То есть quantile $Q(p)$ - такое value random variable $X$, что probability $X$ быть меньше или равным $Q(p)$ равна $p$.

### Common quantiles

1. **Median**: quantile при $p = 0.5$, то есть $Q(0.5)$. Делит dataset на две части по 50%.
2. **Quartiles**: делят dataset на четыре равные части, каждая содержит 25% data:
   - First quartile (Q1): quantile при $p = 0.25$, то есть $Q(0.25)$.
   - Second quartile (Q2): quantile при $p = 0.5$, то есть median.
   - Third quartile (Q3): quantile при $p = 0.75$, то есть $Q(0.75)$.
3. **Percentiles**: quantiles для $p$ от 0.01 до 0.99. Например, 90th percentile - quantile при $p = 0.90$, то есть $Q(0.90)$.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/9.png)

### Calculation

Для заданного dataset шаги вычисления quantile:

1. Отсортировать dataset ascending.
2. Определить position quantile. Для $p$-quantile position $P$:
   $P = np$
   где $n$ - size dataset.
3. Если $P$ integer, то $p$-quantile - average $P$-th и $P+1$-th data points.
4. Если $P$ not integer, то $p$-quantile - $\lceil P \rceil$-th data point, где $\lceil P \rceil$ означает ceiling $P$.

### Applications

Quantiles имеют много applications в statistics:

- описание shape и dispersion data distribution;
- detection outliers;
- standardization и transformation data;
- построение Boxplot для visualization data distribution.

Quantiles - важный инструмент для понимания data distribution, дающий useful information о relative position и distribution features.


### 3.2. Boxplot

Boxplot, также box-and-whisker plot, - statistical chart для показа distribution features data. Он дает intuitive view minimum, first quartile (Q1), median (Q2), third quartile (Q3), maximum и outliers, если они есть. Базовые шаги построения:

### Manual steps for boxplot

1. **Collect data**: сначала нужна группа data для analysis.

2. **Sort**: отсортировать data ascending.

3. **Calculate quartiles**:
   - **Q1**: median нижней половины data, если dataset size odd, median не включается.
   - **Q2 / Median**: median всего dataset.
   - **Q3**: median верхней половины data, если dataset size odd, median не включается.

4. **Determine max и min**:
   - Max: maximum dataset после исключения outliers.
   - Min: minimum dataset после исключения outliers.

5. **Draw box**:
   - Lower bound box - Q1, upper bound - Q3.

6. **Draw median line**:
   - Внутри box провести line, обозначающую median Q2.

7. **Draw whiskers**:
   - Whiskers - lines, выходящие из box и показывающие range data. Обычно ends whiskers - min и max, но если есть outliers, whiskers идут до min/max non-outlier values.

8. **Mark outliers**:
   - Outliers обычно отмечают dots или stars. Это data points outside whiskers.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/10.png)

#### Python (using matplotlib и seaborn):
```python
import seaborn as sns
import matplotlib.pyplot as plt

# 假设data是一个Pandas Series或DataFrame的列
sns.boxplot(data)
plt.show()
```

### 3.3. Kernel Density Estimation

Kernel Density Estimation (KDE) - non-parametric method для оценки Probability Density Function (PDF). Он помещает "kernel" вокруг каждой data point, обычно smooth symmetric function вроде Gaussian function, а затем суммирует эти kernel functions, получая smooth continuous PDF.

### Principle

Пусть есть sample set $\{x_1, x_2, \ldots, x_n\}$, и мы хотим оценить PDF $f(x)$. KDE:

$\hat{f}(x) = \frac{1}{n} \sum_{i=1}^{n} K\left(\frac{x - x_i}{h}\right)$

Где:
- $\hat{f}(x)$ - estimated PDF.
- $K(\cdot)$ - kernel function, non-negative symmetric function, удовлетворяющая $\int K(u) \, du = 1$.
- $h$ - bandwidth, positive number, controlling width kernel function and smoothness estimate.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/11.png)

### Common kernels

1. **Gaussian Kernel**:
   $K(u) = \frac{1}{\sqrt{2\pi}} e^{-\frac{u^2}{2}}$
   Gaussian kernel - самый распространенный kernel function, он smooth и symmetric.

2. **Uniform Kernel**:
   $K(u) = \begin{cases}
   \frac{1}{2} & \text{if } |u| \leq 1 \\
   0 & \text{otherwise}
   \end{cases}$
   Uniform kernel constant при $|u| \leq 1$, иначе 0.

3. **Triangular Kernel**:
   $K(u) = \begin{cases}
   1 - |u| & \text{if } |u| \leq 1 \\
   0 & \text{otherwise}
   \end{cases}$
   Triangular kernel linear при $|u| \leq 1$, иначе 0.

### Bandwidth selection

Выбор bandwidth $h$ сильно влияет на результат KDE. Если bandwidth слишком мал, estimated density будет слишком rugged и overfitted; если слишком велик, estimated density будет слишком smooth и underfitted. Частые методы выбора bandwidth:

1. **Cross-Validation**: выбрать bandwidth, минимизируя difference между estimated density и actual density.
2. **Silverman's Rule of Thumb**: выбрать bandwidth по sample size $n$ и sample standard deviation $\sigma$:
   $h = \left(\frac{4\sigma^5}{3n}\right)^{\frac{1}{5}}$


### 3.4. Violin Plot

Violin Plot - data visualization chart, combining features boxplot и kernel density plot, используемый для показа data distribution.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/12.png)

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/13.png)

### 3.5. Quantile-Quantile Plot

QQ plot - chart для проверки, соответствует ли data некоторому distribution. Он сравнивает quantiles data с theoretical quantiles, чтобы понять, следует ли data определенному distribution.

QQ plot проверяет distribution data через comparison sample quantiles и quantiles theoretical distribution, обычно normal distribution. Конкретнее, sample quantiles, называемые empirical quantiles, paired с corresponding quantiles theoretical distribution, называемыми theoretical quantiles, и эти pairs отображаются на scatter plot.

![alt text](../../../11-第十一章-数学/Probability&Statistics/Probability&Statistics/14.png)

Если sample data follows given theoretical distribution, points на QQ plot должны примерно лежать на straight line; slope этой line равен sample standard deviation, intercept равен sample mean.


## Ссылки

[1] [robability-and-statistics](https://www.coursera.org/learn/machine-learning-probability-and-statistics/home/week/2)
