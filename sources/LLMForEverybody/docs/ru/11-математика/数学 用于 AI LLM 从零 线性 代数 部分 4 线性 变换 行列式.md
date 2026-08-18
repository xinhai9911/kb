---
aliases: ["matematika-dlya-ai-llm-s-nulya-lineynaya-algebra-chast-4-linear-transformations-i-determinant"]
---

Математика для AI/LLM с нуля: линейная алгебра, часть 4, linear transformations и determinant

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Линейная алгебра - одна из базовых математических областей для AI. Владение линейной алгеброй критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по линейной алгебре, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание linear algebra.

## 2. Linear transformation

### 2.1. Singular и non-singular linear transformations

Мы знаем, что matrix можно рассматривать как linear transformation: она maps один vector space в другой vector space. Linear transformation можно разделить на singular и non-singular cases.

- **Non-singular linear transformation**: если linear transformation является bijection, то есть one-to-one correspondence, значит она non-singular. Non-singular linear transformation invertible: через inverse transformation можно map output space обратно во input space.

- **Singular linear transformation**: если linear transformation не является bijection, то есть не one-to-one correspondence, значит она singular. Singular linear transformation не invertible: через inverse transformation нельзя map output space обратно во input space.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/24.png)

Singular linear transformation фактически является dimensionality-reducing linear transformation. После dimensionality reduction ее уже нельзя обратить.

### 2.2. Rank linear transformation

Ранее мы уже изучили rank matrix. Rank matrix - меньшая из column rank и row rank. Rank linear transformation означает dimension output space linear transformation.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/25.png)

## 3. Determinant

### 3.1. Determinant и area

Предположим, у нас есть linear transformation:
$$
\begin{pmatrix}
3 & 1  \\
1 & 2
\end{pmatrix}
$$

Она maps points из two-dimensional space в points другого two-dimensional space. Видно, что исходные четыре coordinate points $(0,0)$, $(1,0)$, $(0,1)$, $(1,1)$ после linear transformation становятся новыми coordinate points $(0,0)$, $(3,1)$, $(1,2)$, $(4,3)$.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/26.png)

Area исходных coordinate points равна 1, area новых coordinate points равна 5. Мы говорим, что эта linear transformation увеличила исходную area в 5 раз. Это 5 и есть determinant matrix (linear transformation).

Можно посмотреть больше singular examples. Например, matrix:

$$
\begin{pmatrix}
1 & 1  \\
2 & 2
\end{pmatrix}
$$

![alt text](../../../11-第十一章-数学/linear-algebra/assest/27.png)

Ее determinant равен 0. Это означает, что linear transformation этой matrix сжимает исходную area до 0, то есть превращает исходную area в line.

Другой пример, matrix:

$$
\begin{pmatrix}
0 & 0  \\
0 & 0
\end{pmatrix}
$$

![alt text](../../../11-第十一章-数学/linear-algebra/assest/28.png)

Ее determinant равен 0. Это означает, что linear transformation этой matrix сжимает исходную area до 0, то есть превращает исходную area в point.

Итоги:

![alt text](../../../11-第十一章-数学/linear-algebra/assest/29.png)

### 3.2. Determinant matrix product

Для двух matrices $A$ и $B$ determinant их product равен product их determinants.

$det(AB) = det(A)det(B)$

### 3.3. Determinant inverse matrix

Для matrix $A$, если она invertible, determinant ее inverse matrix $A^{-1}$ равен reciprocal determinant $A$.

$det(A^{-1}) = \frac{1}{det(A)}$

### 3.4. Determinant identity matrix

Determinant identity matrix равен 1.

$det(I) = 1$


## Ссылки

[1] [machine-learning-linear-algebra](https://www.coursera.org/learn/machine-learning-linear-algebra/home/week/4)


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：数学
