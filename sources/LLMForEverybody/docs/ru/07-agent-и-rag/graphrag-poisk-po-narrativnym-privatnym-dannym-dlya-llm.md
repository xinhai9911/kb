GraphRAG: раскрытие возможностей LLM для поиска по нарративным приватным данным (русский перевод)

https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/

## В самом начале

Некоторое время назад открытый Microsoft GraphRAG вызвал заметный резонанс. Я посмотрел много материалов, и самым ценным из них, пожалуй, оказался собственный блог Microsoft: https://www.microsoft.com/en-us/research/blog/graphrag-unlocking-llm-discovery-on-narrative-private-data/

Материал подробный, поэтому я попробовал перевести его на китайский, надеясь, что это поможет большему числу людей, которым нужна такая информация.

Из-за ограниченного уровня переводчика в переводе неизбежно могут быть ошибки, прошу отнестись с пониманием. Если заметите проблему, пожалуйста, укажите на нее в комментариях, я постараюсь исправить как можно быстрее.

Narrative Private Data в заголовке здесь переведено как нарративные приватные данные; если есть более удачный вариант, буду рад предложениям.

Примечание к чтению: используемый в статье набор данных содержит чувствительные темы. Переводчик только переводит текст; перевод не отражает позицию переводчика.

## Начало основного текста:

Возможно, самый большой вызов для LLM, и одновременно самая большая возможность, состоит в том, чтобы расширить их мощные способности на задачи за пределами обучающих данных и получать сопоставимые результаты на данных, которых LLM никогда не видели. Это открывает новые возможности для исследования данных, например для выявления тем и семантических концепций на основе контекста и набора данных. В этой статье мы представляем GraphRAG, созданный Microsoft Research, как важный шаг вперед в усилении возможностей LLM.

Retrieval-Augmented Generation (RAG) — это техника, которая ищет информацию по пользовательскому запросу и предоставляет результаты как опору для ответа generative AI. Эта техника является важной частью большинства инструментов на базе LLM, а большинство RAG-подходов используют векторную близость как поисковую технику. GraphRAG использует knowledge graph, сгенерированный LLM, и существенно повышает качество вопросов и ответов при анализе документов со сложной информацией. Это опирается на наше недавнее [исследование](https://www.microsoft.com/en-us/research/publication/can-generalist-foundation-models-outcompete-special-purpose-tuning-case-study-in-medicine/), где была отмечена сила prompt augmentation при выполнении discovery на private dataset. (Это предложение из-за особенностей английской формулировки переводится немного тяжеловесно; смысл примерно в том, что при поиске по приватным данным, если хорошо сделать prompt, можно получить более качественные результаты поиска и, как следствие, более хорошие RAG-результаты, прим. переводчика.) Здесь мы определяем private dataset как данные, на которых LLM не обучалась и которых она никогда не видела, например собственные исследования компании, деловые документы или коммуникации. Baseline RAG был создан, чтобы помочь решить эту проблему, но мы наблюдали случаи, где Baseline RAG работает очень плохо. Например:

- Baseline RAG с трудом соединяет отдельные точки. Это происходит, когда для ответа на вопрос нужно пройти по разным фрагментам информации через общие атрибуты, чтобы получить новое синтезированное понимание.
- Baseline RAG плохо справляется, когда его просят всесторонне понять суммарные семантические концепции в крупном наборе данных или даже в одном большом документе.

Чтобы решить эту проблему, техническое сообщество активно разрабатывает способы расширять и усиливать RAG, например [LlamaIndex](https://www.llamaindex.ai/). Новый подход Microsoft Research, GraphRAG, использует LLM для создания knowledge graph на основе private dataset. Затем этот граф используется вместе с graph machine learning, чтобы выполнять prompt augmentation во время запроса. GraphRAG показывает заметный прогресс в ответах на оба типа вопросов, описанных выше, и демонстрирует более высокий уровень интеллекта или владения материалом, чем другие методы, ранее применявшиеся к private dataset.

## Применение RAG к приватному набору данных

Чтобы показать эффективность GraphRAG, сначала воспользуемся [набором данных](https://github.com/zhukovyuri/VIINA) Violence Information from News Articles (VIINA). Этот набор выбран из-за его сложности, наличия разных точек зрения и неполной информации. Это хаотичный реальный тестовый случай, к тому же временной период достаточно свежий, поэтому он не был включен в обучение базовых моделей LLM.

В этом исследовании мы использовали тысячи новостных статей из российских и украинских источников за июнь 2023 года, переведенных на английский, чтобы создать private dataset, на котором мы будем выполнять поиск на базе LLM. Набор данных слишком велик, чтобы поместиться в контекстное окно LLM, поэтому нужен RAG-подход. (Вот она, мягкая сила технологий: можно незаметно вложить свою повестку и распространить ее по всему миру, прим. переводчика.)

Мы начинаем с исследовательского запроса, который задается базовой RAG-системе и нашему новому подходу GraphRAG:

Query: “What is Novorossiya?” Эта часть не переводится

|Baseline RAG|GraphRAG|
| :--- |:--- |
|The term “Novorossiya” is not mentioned in the provided context. However, to provide some information, Novorossiya, or New Russia, is a historical term referring to a region in the south of Ukraine that was conquered by the Russian Empire in the 18th century. In recent years, the term has been revived by Russian-backed separatists in Eastern Ukraine to refer to the territories they claim, but it is not officially recognized as a separate entity by international bodies. |<ol><li>Novorossiya, also known as New Russia, is a term with historical and contemporary significance. Historically, it referred to a region in the southern part of the Russian Empire that is now part of Ukraine. In the contemporary context, it has been used by pro-Russian separatists to refer to certain areas of Ukraine [Data: Entities (6494, 912, 6493)].</li><li>The term Novorossiya has been used in the context of a political movement in Ukraine, particularly by Russian nationalists. This movement has been associated with efforts to destabilize Ukraine and create a so-called “Novorossiya” [Data: Entities (912); Relationships (15211, 15206)]. The term has also been used to denote a separatist state in Ukraine, known as the Federal Republic of Novorossiya (FRN) [Data: Entities (7690)].  </li><ol>|

В этих результатах видно, что обе системы работают хорошо — это показывает класс запросов, где Baseline RAG справляется успешно. Попробуем запрос, который требует соединить точки:

Query: “What has Novorossiya done?”

|Baseline RAG|GraphRAG|
| :--- |:---|
|The text does not provide specific information on what Novorossiya has done.| <ol><li>Novorossiya, a political movement in Ukraine, has been involved in a series of destructive activities, particularly targeting various entities in Ukraine [Entities (6494, 912)]. The movement has been linked to plans to destroy properties of several Ukrainian entities, including Rosen, the Odessa Canning Factory, the Odessa Regional Radio Television Transmission Center, and the National Television Company of Ukraine [Relationships (15207, 15208, 15209, 15210)]. In addition to these, Novorossiya has also been associated with plans to destroy properties of Roshen, the Odessa Conservatory Factory, the Odesa Regional Radio Television Transmission Center, and the National Telecommunications Company of Ukraine [Relationships (8329, 8330, 8331, 8332)]. Furthermore, Novorossiya has been implicated in plans to blow up ATMs of PrivatBank, the largest state bank in Ukraine[Relationships (8335, 8335)].</li><li>The Office of the General Prosecutor in Ukraine has reported on the creation of Novorossiya, indicating the government’s awareness and potential concern over the activities of this movement [Relationships (8264, 8264)]. The destructive activities of Novorossiya have had significant impacts on the targeted entities and have likely contributed to the ongoing tensions and conflicts in the region. /  In summary, Novorossiya has been involved in a series of destructive activities targeting various entities in Ukraine. These activities have had significant impacts on the targeted entities and have likely contributed to the ongoing tensions and conflicts in the region. The Ukrainian government, through the Office of the General Prosecutor, has acknowledged the existence and activities of Novorossiya, indicating a level of concern over the movement’s actions.</li><ol>|

Baseline RAG не смог ответить на этот вопрос. Если посмотреть на исходные документы, вставленные в контекстное окно (см. рисунок ниже), ни один текстовый фрагмент не обсуждает “Novorossiya”, что и приводит к этой проблеме.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/0.png>)

В отличие от этого, подход GraphRAG обнаружил сущность в запросе о Novorossiya. Это позволило LLM получить точку опоры в графе и, переходя по ссылкам на исходный подтверждающий текст, вывести более качественный ответ с источниками. Например, рисунок 2 ниже показывает точное содержимое, которое LLM использовала для сгенерированного LLM утверждения “Novorossiya has been implicated in plans to blow up ATMs”. Мы видим фрагмент из исходного документа, переведенного на английский, который LLM использовала для поддержки этого утверждения через связь между двумя сущностями в графе.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/1.png>)

Используя сгенерированный LLM knowledge graph, GraphRAG существенно улучшает “retrieval”-часть RAG: контекстное окно заполняется более релевантным содержимым, что дает лучшие ответы и фиксирует источники доказательств.

Возможность доверять результатам, сгенерированным LLM, и проверять их всегда важна. Нас интересует, являются ли результаты корректными, связными и точно отражают ли они содержание исходного материала. GraphRAG при генерации каждого ответа предоставляет происхождение или базовую информацию об источниках. Он показывает, что ответ основан на наборе данных. То, что источники цитирования для каждого утверждения доступны в любой момент, также позволяет пользователю быстро и точно сверить вывод LLM напрямую с исходным материалом.

Однако это еще не все, чего можно добиться с GraphRAG.

## Рассуждение по всему набору данных

Baseline RAG с трудом обрабатывает запросы, для которых нужно обобщить информацию из всего набора данных, чтобы получить ответ. Запросы вроде “Какие 5 главных тем в данных?” работают плохо, потому что Baseline RAG опирается на векторный поиск семантически похожего текстового содержимого внутри набора данных. В самом запросе нет ничего, что направило бы его к правильной информации.

Но с GraphRAG мы можем отвечать на такие вопросы, потому что структура knowledge graph, сгенерированного LLM, сообщает нам структуру всего набора данных и его темы. Это позволяет организовать private dataset в заранее суммированные осмысленные семантические кластеры. При ответе на пользовательский запрос LLM использует эти кластеры, чтобы обобщить темы.

Мы иллюстрируем способность к рассуждению по всему набору данных, задавая обеим системам следующий вопрос:

Query: “What are the top 5 themes in the data?“

|Baseline RAG|GraphRAG|
| :--- |:--- |
|<ol><li>Improving the quality of life in cities and urban development.</li><li>The meeting between Vladimir Putin and the President of the United Arab Emirates, Mohammed bin Zayed Al Nahyan.</li><li>The National Rating of the Investment Climate in the Regions of Russia.</li><li>The state of the Russian economy and the growth of domestic brands.</li><li>The discussion on the meaning of life and the role of science in understanding it. </li></ol> |<ol>The data presents a wide range of themes, but the top five most prevalent themes can be identified as follows: <li>Conflict and Military Activity: A significant portion of the data revolves around the ongoing conflict in Ukraine, with numerous reports detailing military activities, occupations, and attacks by various entities. This theme includes the actions of the Ukrainian military, Russian forces, and various other military units and entities [Data: Reports (513, 241, 151, 493, 343, +more)].</li><li>Political and Governmental Entities: Many reports focus on political figures and governmental entities, highlighting their roles, relationships, and actions in the context of the current situation. This includes entities like the Kremlin, the President of Ukraine, the US State Department, and various regional administrations [Data: Reports (98, 493, 265, 129, 196, +more)]. </li><li>Infrastructure and Environmental Concerns: Several reports highlight potential environmental impacts and infrastructure threats. These include potential environmental damage due to industrial activities, flooding crises, and threats to infrastructure due to military conflicts [Data: Reports (308, 154, 201, 348, 216, +more)].</li><li>Community Analysis and Threat Assessment: Several reports provide detailed analyses of specific communities, often centered around a particular location or entity. These analyses typically discuss the key entities within the community, their relationships, and any associated threats. Many reports also include assessments of potential threats associated with the entities or situations they discuss [Data: Reports (323, 596, 518, 583, 179, +more)]. </li><li>Health, Humanitarian Concerns, and Emergency Situations: Some reports focus on health and humanitarian issues, such as the Shereshevsky-Turner Syndrome community and the potential risk of intestinal diseases in the Odessa region. The data also covers emergency situations, including natural disasters, accidents, and attacks [Data: Reports (204, 149, 372, 154, 532, +more)]. <li>These themes provide a comprehensive overview of the current situation, highlighting the complexity and interconnectedness of the issues at hand.</li><ol>

Глядя на результат Baseline RAG, мы видим, что перечисленные темы имеют мало отношения к войне между двумя странами. Как и ожидалось, векторный поиск извлек нерелевантные тексты, которые были вставлены в контекстное окно LLM. Включенные результаты, вероятно, связаны со словом “темы”, что привело к не слишком полезной оценке происходящего в наборе данных.

По результату GraphRAG ясно видно, что ответ намного лучше соответствует ситуации во всем наборе данных. Ответ приводит пять основных тем, наблюдаемых в данных, и поддерживающие детали. Ссылочные отчеты заранее генерируются LLM для каждого семантического кластера в GraphRAG, а затем обеспечивают происхождение исходного материала.

## Создание knowledge graph, сгенерированного LLM

Мы отмечаем базовый процесс, лежащий в основе GraphRAG. Он строится на нашем предыдущем [исследовании](https://www.microsoft.com/en-us/worklab/patterns-hidden-inside-the-org-chart) с использованием graph machine learning и на [GitHub-репозитории](https://github.com/graspologic-org/graspologic): (могут спросить на собеседовании, прим. переводчика.)

- LLM обрабатывает весь private dataset, создает ссылки на все сущности и отношения в исходных данных, а затем использует эти ссылки для создания сгенерированного LLM knowledge graph.
- Затем этот граф используется для создания кластеризации снизу вверх, которая иерархически организует данные в семантические кластеры (на рисунке ниже они показаны разными цветами). Такое разбиение позволяет заранее суммировать семантические концепции и темы, что помогает целостно понимать набор данных.
- Во время запроса обе эти структуры используются, чтобы предоставить материал для контекстного окна LLM при ответе на вопрос.

![alt text](<../../../07-第七章-Agent/assest/GraphRAG 解锁大模型对叙述性私人数据的检索能力（中文翻译）/2.jpg>)

На рисунке выше показан пример визуализации этого Graph. Каждый круг представляет сущность, например человека, место или организацию; размер сущности показывает количество связей у этой сущности, а цвет — группировку похожих сущностей. Цветовое разбиение — это метод кластеризации снизу вверх, построенный поверх структуры графа; он позволяет отвечать на вопросы разных уровней абстракции.

## Метрики результатов

Приведенные выше примеры представляют устойчивое улучшение GraphRAG на нескольких наборах данных в разных предметных областях. Для оценки мы используем LLM-оценщик, который определяет победителя в парном сравнении между GraphRAG и Baseline RAG, тем самым измеряя это улучшение. Мы используем набор качественных метрик, включая полноту (comprehensiveness, полнота в рамках неявного контекстного фрейма вопроса), расширение возможностей человека (human empowerment, предоставление поддерживающих исходных материалов или другого контекста) и разнообразие (diversity, разные точки зрения или углы на заданный вопрос). Предварительные результаты показывают, что GraphRAG стабильно превосходит Baseline RAG по этим метрикам.

Помимо относительного сравнения, мы также используем [SelfCheckGPT](https://arxiv.org/pdf/2303.08896) для абсолютного измерения верности, чтобы помочь убедиться, что результаты основаны на исходном материале, являются правдивыми и связными. Результаты показывают, что верность GraphRAG сопоставима с Baseline RAG. Сейчас мы разрабатываем оценочный фреймворк для измерения качества по указанным выше категориям вопросов. Он будет включать более надежные механизмы генерации тестовых наборов вопросов и ответов, а также другие метрики, например точность и контекстную релевантность.

## Следующие шаги

Комбинируя сгенерированный LLM knowledge graph и graph machine learning, GraphRAG позволяет отвечать на важные вопросы, которые невозможно решить одним только Baseline RAG. После применения этой технологии в разных сценариях, включая социальные сети, новостные статьи, продуктивность на рабочем месте и химию, мы уже увидели обнадеживающие результаты. В будущем мы планируем, продолжая применять эту технологию, тесно сотрудничать с клиентами в разных новых областях, одновременно работая над метриками и надежной оценкой. По мере продолжения исследования мы рассчитываем поделиться дополнительной информацией.


## Примечания

[1] В этом сравнении мы использовали [Q&A](https://python.langchain.com/v0.1/docs/use_cases/question_answering/) LangChain как Baseline RAG — известный репрезентативный пример такого RAG-инструмента, широко используемого сегодня.

[2] Этот набор данных содержит чувствительные темы. Единственная цель выбора этого набора данных — продемонстрировать инструменты анализа данных, которые показывают всю релевантную информацию, включая ее источники. Эти инструменты основаны на информации из набора данных и позволяют пользователям быстрее приходить к обоснованным выводам на основе противоположных точек зрения из украинских (unian) и русских (ria) новостных статей, каждая из которых берется на языке оригинала. Инструменты подсвечивают источник каждого утверждения и могут использоваться для определения происхождения информации.

## Конец основного текста


## Добро пожаловать на мой GitHub и в WeChat-канал — некогда объяснять, быстро на борт!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

В репозитории есть исходный Markdown-файл, он полностью открыт, буду рад Star и Fork!
