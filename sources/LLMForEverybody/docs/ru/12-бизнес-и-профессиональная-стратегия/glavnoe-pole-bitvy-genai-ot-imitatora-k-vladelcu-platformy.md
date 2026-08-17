- Декомпозиция -> барьер -> ядро -> связывание: четыре шага победителя

Популярность generative AI не вызывает сомнений: внезапный взлет ChatGPT зажег глобальный интерес. Следом в этом году появились всевозможные продукты с "Agent". Но за внешним блеском скрывается жесткая реальность: **простое копирование не создает настоящего moat**.

Тогда в этом, казалось бы, переполненном red ocean, **кто станет небольшой группой финальных победителей**? Как перейти от имитатора к "platform controller", который определяет будущую расстановку сил?

Вокруг этого ключевого вопроса статья пытается описать flow capture value в generative AI и выделить четыре ключевых шага к успеху. Сегодня подробно разберем эту "roadmap победителя".

## 1. Шаг первый: нарезать пирог - искать не "широко и все", а "глубоко и точно" (unbundle)

Foundation models вроде Qwen и DeepSeek сильны в "горизонтальных универсальных способностях": могут общаться, писать, программировать. Однако **настоящие пользовательские потребности часто являются "вертикальными specific scenarios"**:

- маркетологам нужен AI, который создает high-conversion copy;
- программистам нужен AI, который точно генерирует и debug code;
- дизайнерам нужен AI tool, понимающий инструкции по конкретному style.

Так появляются "Agent applications". По сути, они надевают на foundation model "одежду" конкретного сценария: через тщательно спроектированный Prompt Engineering, с помощью Agent или workflow и user interface (UI), они раскладывают general ability на определенную vertical task.

Смысл: снижается порог использования для пользователя и появляется готовое out-of-the-box solution.

Ловушка: **простая упаковка имеет очень низкий барьер, имитаторы быстро набегут, и в итоге начнется homogeneous competition**. Одной "одежды" недостаточно для core advantage.


## 2. Шаг второй: построить барьер - создать собственный "data flywheel" (vertical advantage)

Как эволюционировать от "копируемой обертки" к "трудно пробиваемому барьеру"? Ключ - построить Vertical Advantage, self-reinforcing flywheel loop:

1. Отличный prompt engineering и user experience: привлекают target users к вашему vertical application.
2. Глубокое участие пользователей: users часто используют продукт, формируя high stickiness.
3. Захват proprietary domain data: когда users решают specific problems через ваше приложение, вы собираете много уникальных high-value vertical domain data, например конкретные детали того, как юристы используют AI для правки contract templates, или как дизайнеры предпочитают корректировать style. Такие data другим трудно получить.
4. Fine-tuning и optimization модели: используя эти unique domain data, вы постоянно fine-tune foundation model, делая ее все сильнее и компетентнее в вашей domain.
5. Улучшение user experience: чем лучше model performance, тем довольнее users, тем чаще они используют продукт, тем больше data возникает... flywheel продолжает ускоряться.

Core competitiveness: ядро flywheel - **сочетание накопления domain-specific data и способности model iteration**. Это требует тесной совместной работы product team и technical/model team, чтобы быстро iteratively улучшать product и model по realtime user feedback. В крупных организациях departmental barriers часто становятся самым большим препятствием на этом пути.

Кратко: **через unbundle выйти на рынок, через data flywheel построить почти непреодолимый vertical barrier**. Вы больше не "необязательная упаковка", а игрок с core competitiveness, глубоко работающий в конкретной domain.

![alt text](../../../12-第十二章-企业与个人思考/assest/GenAI浪潮下的终极战场：如何从模仿者蜕变为“平台掌控者”？/1.png)

## 3. Шаг третий: овладеть ядром - найти "жизненную артерию" workflow (core creative activity)

Построение vertical barrier (шаг 2) - основа выживания. Но чтобы действительно захватить большую value и заставить VC нервно ускорить пульс, нужен более амбициозный шаг: rebundling.

Unbundle похоже на disruption: разрезает пирог. Rebundling перестраивает value chain и становится центром нового пирога.

Лучший пример для понимания rebundling - WeChat:
- Старт: unbundle разрушает традиционное. WeChat сначала вошел как vertical replacement для SMS, то есть basic communication tool.
- Захват core horizontal capabilities: он быстро овладел двумя крайне universal horizontal capabilities - communication и payment.
- Создание новой platform: опираясь на эти две core capabilities, WeChat построил новый platform layer поверх mobile operating system.
- Rebundling: в итоге official accounts, mini programs, local services, games и множество других functions/services были bundled в эту новую platform. WeChat стал управлять relationship между users и огромным количеством services, превратившись в super hub digital life.

В generative AI ключ к rebundling - identify и control The Core Creative Activity в workflow этой domain:

- Различать predictive AI vs. generative AI:
  - У predictive AI, например recommendation algorithms, ядро - Core Decision: решить, "что рекомендовать".
  - У generative AI ядро - "creation". Core creative activity - тот creative stage, который определяет final output и несет наибольшую value.

- Где core в industry?
  - Architecture design: concept development, final structural safety review.
  - Drug discovery: target discovery, molecular structure design.
  - Content creation: generation of core creative concept и final shaping/approval.
  - Software development: core architecture design, complex logic construction.

Кто контролирует core creative activity, тот получает ключ к роли нового hub. Другие tools будут строиться, интегрироваться или зависеть от этого core.


## 4. Шаг четвертый: создать hub - стать "definer" нового порядка (rebundling)

После того как вы ясно поняли, какой core creative activity хотите контролировать, как превратить себя в новый platform hub этой domain? Нужны три key competitive advantages, которые могут накладываться:

1. Scenario Advantage: насколько глубоко ваш product embedded в target scenario? Обязаны ли users проходить через ваш product, чтобы выполнить core creative activity? Вы контролируете entrance core workflow.

2. Intelligence Advantage: есть ли у вас powerful model, best-performing на этой core activity и specialized под эту domain? Обычно это результат proprietary data и continuous fine-tuning, накопленных вашим data flywheel.

3. Relationship Advantage: есть ли у вас deep relationships с key people, выполняющими core activity, например top designers, researchers, engineers? Доверяют ли они вам и выбирают ли ваши tools первыми?

## 5. Roadmap победителя: от входа до доминирования

Четыре ясных шага, каждый строится на предыдущем:

1. Unbundle: использовать сильную foundation model и точно войти в vertical market, где вы можете закрепиться.

2. Vertical Advantage: построить в vertical domain "data flywheel", сформировав трудно копируемое vertical advantage и moat.

3. Core Creative Activity: identify и lock core creative activity в workflow этой vertical domain.

4. Rebundle: опираясь на core advantages в workflow, intelligence, relationships или их combination, control core activity, стать new hub и lead next-generation value chain в этой domain.


## 6. Размышление: где ваше поле битвы?

Вернемся к industry, которой вы занимаетесь или которую глубоко изучаете:

1. Что именно является самой valuable "core creative activity"? Concept development? Structural design? Gene screening? Creative direction?

2. Посмотрите вокруг: кто, existing giant, new player или... вы сами, вероятнее всего сможет через AI усилить или даже control эту core activity?

3. Смогут ли они или вы успешно выполнить rebundling и стать key hub, defining future?

## Ссылки

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)
