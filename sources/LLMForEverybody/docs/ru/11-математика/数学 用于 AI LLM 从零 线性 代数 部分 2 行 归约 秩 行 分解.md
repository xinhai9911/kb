---
aliases: ["matematika-dlya-ai-llm-s-nulya-lineynaya-algebra-chast-2-row-reduction-rank-row-echelon"]
---

Математика для AI/LLM с нуля: линейная алгебра, часть 2, matrix row reduction, rank и row echelon form

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Линейная алгебра - одна из базовых математических областей для AI. Владение линейной алгеброй критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по линейной алгебре, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание linear algebra.


## 2. Matrix Row Reduction

### 2.1. System of two linear equations

В elementary algebra мы начинаем с system of two linear equations, затем постепенно переходим к systems of three, four и, наконец, n linear equations.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/7.jpeg)

В higher algebra / linear algebra matrix row reduction означает row transformations соответствующей coefficient matrix при решении system of equations методом elimination.

### 2.2. Row operations

![alt text](../../../11-第十一章-数学/linear-algebra/assest/8.png)

На рисунке выше мы решаем system of two linear equations. Обратите внимание на row transformations соответствующей coefficient matrix.

Здесь появляются два новых термина:

1. Row echelon form
2. Reduced row echelon form

- `echelon` - французское слово, означающее "ступень" или "лестничная форма". Это понятие часто встречается в математике, например echelon sequence, echelon function и так далее.

## 3. Rank of a Matrix

### 3.1. Matrix row operations, сохраняющие singularity

- Если вы не знаете, что такое singularity, см. предыдущую статью. Если коротко, singular matrix - это matrix с determinant 0.

1. Поменять строки местами
2. Умножить строку на non-zero constant
3. Добавить к строке multiple другой строки

### 3.2. Rank

Снова воспользуемся аналогией с группой предложений:

![alt text](../../../11-第十一章-数学/linear-algebra/assest/9.png)

На рисунке выше первая system содержит два предложения, вторая system содержит два повторяющихся предложения, а третья system содержит два предложения без информации.

Мы говорим, что rank первой system равен 2, rank второй равен 1, rank третьей равен 0.

## 3.3. Связь rank и solutions system

![alt text](../../../11-第十一章-数学/linear-algebra/assest/10.png)

Для трех systems выше видно: system с rank=2 имеет unique solution; system с rank=1 имеет infinitely many solutions, но на одной line; system с rank=0 имеет infinitely many solutions на plane.

Как показано ниже:

![alt text](../../../11-第十一章-数学/linear-algebra/assest/11.png)

$$rank =2-(размерность пространства решений) $$

## 4. Row Echelon Form

Row echelon form - это matrix, где первый non-zero element строки равен 1, а первый non-zero element каждой следующей строки расположен правее первого non-zero element предыдущей строки. Посмотрим несколько примеров:

![alt text](../../../11-第十一章-数学/linear-algebra/assest/12.png)

- `pivot` в английском означает "ось", "опора"; в контексте linear algebra переводится как `pivot element` / `ведущий элемент`.

### 4.1. Reduced Row Echelon Form

Reduced row echelon form означает, что pivot row echelon form равен 1, а все остальные elements в column этого pivot равны 0.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/13.png)

## 5. Gauss Elimination Algorithm

Gauss elimination - метод решения systems of linear equations. Его базовая идея: через row transformations привести coefficient matrix к row echelon form, а затем решить через back substitution.

- Метод назван в честь математика Gauss, улучшен Al-Khwarizmi и опубликован во Франции, но впервые встречается в китайском классическом труде `The Nine Chapters on the Mathematical Art`, созданном примерно в 150 году до н. э.

Augmented Matrix - это matrix, полученная объединением coefficient matrix и constants matrix.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/14.png)

Через Gauss elimination в итоге получаем такой результат:

![alt text](../../../11-第十一章-数学/linear-algebra/assest/15.png)

После back substitution получаем solution системы уравнений.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/16.png)

Ниже Python-код Gauss elimination:

```python
def gaussian_elimination(A, b):
    n = len(A)

    # Augment the matrix A with the vector b
    for i in range(n):
        A[i].append(b[i])

    # Forward elimination
    for i in range(n):
        # Find the pivot
        max_row = i
        for k in range(i+1, n):
            if abs(A[k][i]) > abs(A[max_row][i]):
                max_row = k
        # Swap the rows
        A[i], A[max_row] = A[max_row], A[i]

        # Make all rows below this one 0 in current column
        for k in range(i+1, n):
            c = -A[k][i] / A[i][i]
            for j in range(i, n+1):
                if i == j:
                    A[k][j] = 0
                else:
                    A[k][j] += c * A[i][j]

    # Back substitution
    x = [0 for _ in range(n)]
    for i in range(n-1, -1, -1):
        x[i] = A[i][n] / A[i][i]
        for k in range(i-1, -1, -1):
            A[k][n] -= A[k][i] * x[i]

    return x

# 示例使用
A = [
    [2, 1, -1],
    [-3, -1, 2],
    [-2, 1, 2]
]
b = [8, -11, -3]

solution = gaussian_elimination(A, b)
print("解:", solution)
```

## Ссылки

[1] [machine-learning-linear-algebra](https://www.coursera.org/learn/machine-learning-linear-algebra/home/week/2)

[2] [高斯消元法](https://zh.wikipedia.org/wiki/%E9%AB%98%E6%96%AF%E6%B6%88%E5%8E%BB%E6%B3%95)


## Подписывайтесь на мой GitHub и WeChat Official Account [Настоящий корабль Тесея]. Некогда объяснять, все на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходные Markdown-файлы. Все полностью open source, буду рад вашим Star и Fork!


---

## 📚 相关概念

[[concepts/Transformer 架构|Transformer 架构]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：数学
