---
aliases: ["matematika-dlya-ai-llm-s-nulya-lineynaya-algebra-chast-5-basis-eigenvalues-eigenvectors"]
---

Математика для AI/LLM с нуля: линейная алгебра, часть 5, basis, eigenvalues и eigenvectors

## 1. Введение в серию

AI - междисциплинарная область на стыке естественных наук и engineering, а прочная математическая база помогает понимать суть алгоритмов.

Линейная алгебра - одна из базовых математических областей для AI. Владение линейной алгеброй критически важно для понимания алгоритмов и моделей deep learning. В этой серии мы разберем знания по линейной алгебре, необходимые для AI large models, чтобы лучше понимать принципы и приложения больших моделей.

Мы будем уделять внимание базовым понятиям, а ключевые математические термины снабжать английскими названиями для лучшего понимания. Также поделимся некоторыми вещами, которым обычно не учат в университете, чтобы помочь построить интуитивное понимание linear algebra.

## 2. Basis and Span

- В разных papers можно встретить `Basis` и `Bases`. В английском `basis` означает "основа; основание; главный компонент; базовый принцип", а в linear algebra переводится как `basis`. Plural form `basis` - `bases`. Еще одно слово, которое легко спутать, - `base`; его plural form тоже `bases`.

### 2.1. Basis

Basis - набор basic vectors vector space; через их linear combination можно получить любой vector этого vector space. В two-dimensional space можно использовать два linearly independent vectors для представления этого space: эти два vectors и являются basis этого space.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/30.png)

### 2.2. Span

Span - множество всех возможных linear combinations в vector space. В two-dimensional space можно использовать два linearly independent vectors для представления этого space, а span этих двух vectors и есть этот space.

### 2.3. Eigenbases

Eigenbasis - особый набор basis, на который стоит обратить внимание, потому что он обладает специальными свойствами.

- Слово `eigen` происходит из немецкого и буквально означает "свой" (own). В mathematics и physics `eigen` обычно связано с "intrinsic", "proper" или "characteristic" и описывает свойства, внутренне присущие system или object.
В начале XX века великий немецкий математик Hilbert впервые использовал слово `eigenvalue` для обозначения characteristic value. Из-за огромного влияния Hilbert сейчас `eigenvalue` стало самым распространенным словом в mathematics и используется чаще, чем англо-французское `characteristic value`.

Для matrix (linear transformation):
$$
\begin{pmatrix}
3 & 1  \\
1 & 2
\end{pmatrix}
$$

Она maps points из two-dimensional space в points другого two-dimensional space. Видно, что исходные четыре coordinate points $(0,0)$, $(1,0)$, $(0,1)$, $(1,1)$ после linear transformation становятся новыми coordinate points $(0,0)$, $(3,1)$, $(1,2)$, $(4,3)$.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/31.png)

На этой two-dimensional plane существует бесконечно много bases (vector groups), но среди них есть специальный basis (vector group): после применения этой matrix direction этого basis не меняется, меняется только length. Этот basis называется eigenbasis.

***Смысл***:
1. Мы знаем, что любой vector на plane (Span) можно выразить через linear combination некоторого basis;
2. значит любой vector, конечно, можно выразить через linear combination eigenbasis;
3. действие linear transformation на любой vector равно действию на linear combination eigenbasis;
4. linear transformation, действуя на eigenbasis, только **меняет length eigenbasis**, а direction остается прежним;
5. через eigenbasis можно упростить вычисления linear transformation.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/33.png)

$$ A =
\begin{pmatrix}
2 & 1  \\
0 & 3
\end{pmatrix}
$$

eigenbasis для нее: $(1,0),(1,1)$

$v$ = $(3,2)$

$(3,2) = 1*(1,0)+2*(1,1)$

$Av$ = $A(3,2)$ = $A*1*(1,0)+A*2*(1,1)$ = $1*A(1,0)+2*A(1,1)$ = $1*2*(1,0)+2*3*(1,1)$ = $(2,0)+(6,6)$ = $(8,6)$

## 3. Eigenvalues and Eigenvectors

Указанный выше eigenbasis и мера того, что он **меняет length eigenbasis**, при дальнейшем разборе дают eigenvectors и eigenvalues.

![alt text](../../../11-第十一章-数学/linear-algebra/assest/34.png)

Метод вычисления eigenvectors и eigenvalues - решить characteristic polynomial matrix.

- `Characteristic` и `Eigen` - две математические формы выражения на английском и немецком; смысл одинаковый.

Definition characteristic polynomial:
$$ det(A-\lambda I) = 0 $$

## Ссылки

[1] [machine-learning-linear-algebra](https://www.coursera.org/learn/machine-learning-linear-algebra/home/week/3)
