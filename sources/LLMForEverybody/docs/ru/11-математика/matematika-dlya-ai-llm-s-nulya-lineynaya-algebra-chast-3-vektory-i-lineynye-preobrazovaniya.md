Математика для AI/LLM с нуля: линейная алгебра, часть 3, vectors и linear transformations

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Линейная алгебра - одна из базовых математических областей для AI. Владение линейной алгеброй критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по линейной алгебре, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание linear algebra.


## 2. Vector

Vector - математический объект, имеющий magnitude и direction. Он широко используется в physics, engineering и mathematics для представления величин с направлением, например force, velocity и displacement. Vector обычно изображают стрелкой: длина стрелки показывает magnitude (или norm), направление стрелки - direction.

### 2.1. Operations on Vectors

Vector addition означает сложение двух vectors, в результате которого получается новый vector. Vector addition удовлетворяет commutative и associative laws.

Vector subtraction означает вычитание одного vector из другого, в результате которого получается новый vector.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/17.png)

### 2.2. Distance

L1-norm и L2-norm - два распространенных метода вычисления distance:

L1-norm, в machine learning также Manhattan distance, - сумма absolute values всех elements vector.

L2-norm, в machine learning также Euclidean distance, - square root суммы squares всех elements vector.

Cosine similarity - cosine угла между двумя vectors.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/18.png)

### 2.3. Dot Product

Dot product - scalar, полученный при умножении двух vectors. Геометрический смысл dot product - projection одного vector на другой.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/19.png)

У dot product есть две формы записи: $x·y$ и $<x,y>$

![alt text](../../../11-第十一章-数学/linear-algebra/assest/20.png)

### 2.4. Hadamard Product

Операция, при которой перемножаются corresponding elements двух vectors и получается новый vector, называется **Hadamard product**, также **element-wise product** или **Schur product**. Эта операция очень часто встречается в mathematics, physics и engineering, особенно в matrix theory, signal processing и large models.

Definition Hadamard product:

Пусть есть два vectors одинаковой размерности $\mathbf{a} = [a_1, a_2, \ldots, a_n]$ и $\mathbf{b} = [b_1, b_2, \ldots, b_n]$. Их Hadamard product - новый vector $\mathbf{c} = [c_1, c_2, \ldots, c_n]$, где каждый element $c_i$ равен product corresponding elements $a_i$ и $b_i$:

$c_i = a_i \cdot b_i$

для всех $i = 1, 2, \ldots, n$.

## 3. Linear Transformations

Matrix-vector multiplication - это linear transformation, которая maps один vector в другой. Result matrix-vector multiplication - новый vector.

### 3.1. Rank и linear transformation

Предположим, у нас есть matrix:
$$
\begin{pmatrix}
3 & 1  \\
1 & 2
\end{pmatrix}
$$

Мы говорим, что фактически это linear transformation, потому что она maps один vector в другой. Как это понять?

В исходном two-dimensional space есть vector $\begin{pmatrix} 1 \\ 1 \end{pmatrix}$ с coordinates $(1,1)$. Когда мы умножаем этот vector на matrix, получаем новый vector $\begin{pmatrix} 5 \\ 3 \end{pmatrix}$ с coordinates $(4,3)$.


Точно так же для трех других coordinate points $(0,0)$, $(1,0)$, $(0,1)$ получаем новые points $(0,0)$, $(3,1)$, $(1,2)$.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/21.png)

Это эквивалентно linear transformation исходной coordinate system.

- Некоторые могли заметить, что area parallelogram, образованного новыми points $(0,0)$, $(3,1)$, $(1,2)$, $(4,3)$, как раз равна rank matrix. Это совпадение?

### 3.2. The identity matrix

`identity` в английском означает "идентичность", а в математике также identity. The identity matrix означает matrix, умножение которой на vector дает тот же vector, что был исходно.

Identity matrix - square matrix, у которой diagonal elements равны 1, а все остальные elements равны 0. Обычно identity matrix обозначают $I$.

### 3.3. Inverse

Matrix, умноженная на свою inverse matrix, дает identity matrix.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/22.png)

Только non-singular matrix является invertible; singular matrix не invertible. Почему? Добро пожаловать в следующую статью.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/23.png)

## Ссылки

[1] [machine-learning-linear-algebra](https://www.coursera.org/learn/machine-learning-linear-algebra/home/week/3)


## Подписывайтесь на мой GitHub и WeChat Official Account [Настоящий корабль Тесея]. Некогда объяснять, все на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Все полностью open source, буду рад вашим Star и Fork!
