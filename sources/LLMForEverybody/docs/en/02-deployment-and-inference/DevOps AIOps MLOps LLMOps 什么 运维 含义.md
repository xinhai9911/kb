---
aliases: ["devops-aiops-mlops-llmops-what-do-these-ops-mean"]
---

# DevOps, AIOps, MLOps, LLMOps: what do these Ops mean?

You may have seen these terms often, and AIOps and MLOps may even have blended together in your head. Below, we will unpack what each of these Ops means. But before we start, let's first look at CI/CD.

## 0. CI/CD

CI/CD is short for Continuous Integration and Continuous Delivery. CI/CD is a software development practice whose goal is to improve development-team efficiency and quality by automating software build, test, and deployment.

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/00.png>)

***Continuous Integration (CI)***:

- Goal: integrate code changes into the main branch frequently.
- Practice: developers regularly, usually several times a day, merge code changes into a shared repository. Every commit is checked by automated builds and automated tests to make sure the change does not break existing functionality.
- Tools: common tools include version-control systems such as `Git`; build tools such as `Maven` and `Gradle`; automated testing tools such as `JUnit` and `NUnit`; and continuous integration servers such as `Jenkins`, `Travis CI`, and `GitLab CI`.

***Continuous Delivery/Deployment (CD)***:

- Goal: make sure the software can be deployed to production at any time.
- Practice: based on continuous integration, continuous delivery adds automated deployment stages to test, staging, or production environments. This includes automating the deployment process, but it does not necessarily mean every change is released to production immediately.
- Tools: besides continuous integration tools, deployment tools such as `Ansible`, `Chef`, and `Puppet` are used, along with configuration-management tools such as `Terraform` and `CloudFormation`.

## 1. DevOps

The history of DevOps goes back to around 2007, when software development and IT operations communities began worrying about the traditional development model. In that model, developers who wrote code and operations specialists who deployed and maintained that code worked independently. The term DevOps comes from "development" and "operations," and reflects the merging of these areas into one continuous process. The DevOps movement started gaining popularity around 2007 to 2008. One important milestone was DevOpsDays, organized by Patrick Debois in Belgium, which helped spread DevOps ideas around the world.

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/01.png>)

Key DevOps values:

- Automation: use automated tools and processes to reduce manual work, improve efficiency, and lower the number of errors.
- Continuous integration/continuous deployment (CI/CD): integrate code changes into the main branch frequently and release to production quickly through automated tests and deployment processes.
- Agile development: use agile methods such as `Scrum` or `Kanban` to respond quickly to change and continuously deliver value.
- Monitoring and feedback: monitor system performance and user feedback in real time, so problems can be found and solved quickly.
- Culture and communication: encourage open communication and collaboration between team members, breaking down the traditional barriers between departments.

## 2. AIOps

AIOps is short for `Artificial Intelligence for IT Operations`. It is a practice that uses artificial intelligence and machine learning technologies to improve IT operations. AIOps aims to improve the efficiency and quality of IT operations through automation and intelligence.

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/02.png>)

The key goal of AIOps is to extract valuable information from huge volumes of operational data, quickly detect failures, diagnose them accurately, and automatically fix them, improving IT-system reliability and operational efficiency.

The key components of AIOps include data collection, storage, analysis, intelligent decision-making, and automated reactions based on that data. Usually this touches several areas:

- Data sources: an AIOps platform needs to collect data from different parts of IT infrastructure, applications, performance-monitoring tools, and service-ticket systems.

- Big data analysis: use Big Data technologies to process and analyze collected data at scale, finding and predicting potential problems.

- Machine learning: apply machine learning algorithms to better understand and analyze data, enabling more accurate failure prediction and root-cause analysis.

- Automation: automatically trigger responses based on analysis results, reducing manual intervention and improving problem-handling speed and efficiency.

- Visualization and reporting: present analysis results and operational status through visualization tools, helping IT teams better understand system performance and make decisions.

Using AIOps helps companies manage and maintain complex IT environments during digital transformation, improve service quality, lower operating costs, and strengthen their ability to adapt to business change.

## 3. MLOps

MLOps, or `Machine Learning Operations`, is a set of workflow practices designed to simplify deployment and maintenance of machine learning (`ML`) models. It combines DevOps and GitOps principles, and through automation and process standardization, it integrates machine learning models into the software development process. The goal of MLOps is to improve model quality and accuracy, simplify management, avoid data drift, improve data scientist efficiency, and bring value to the whole team.

> Tip: in industry, people first thought about AI helping operations, and only later realized that AI itself also needs operations. So the name "AIOps" was first taken by AI for IT operations, and operations for AI models later had to be called "MLOps."

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/03.png>)

Key components of MLOps:

- Version control: track changes in machine learning assets so results can be reproduced and previous versions can be restored when needed.
- Automation: automatically run stages of the ML pipeline to ensure reproducibility, consistency, and scalability.
- Continuous X: includes continuous integration (CI), continuous delivery (CD), continuous training (CT), and continuous monitoring (CM), supporting ongoing model improvement and deployment.
- Model management: manage different aspects of ML systems to improve efficiency, including team collaboration, data security, and compliance.

Benefits of MLOps include shorter time to market, higher work efficiency, effective model deployment, and cost savings. MLOps lets data scientists, engineers, and IT teams collaborate closely, iterate quickly, and deploy models while keeping production performance and reliability under control.

At this point, the responsibility boundary of algorithm engineers has already expanded to model deployment and maintenance.

## 4. LLMOps

With the rise of large models, LLMOps (`Large Language Model Operations`) has gradually become a new popular topic. LLMOps means operations for large language models, and its goal is to simplify deployment and maintenance of large models while improving their quality and efficiency. The closest comparable concept is MLOps.

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/04.png>)

First, let's compare traditional software applications, including machine learning, with large-model applications:

| | Traditional software applications | Large-model applications |
| :---: |:----:| :----: |
| Characteristic | Predefined rules | Probability and prediction |
| Output | Deterministic: same input, same output | Non-deterministic: same input, many possible outputs |
| Testing | One output, one exact output | One input, many accurate or inaccurate possible outputs |
| Acceptance criteria | Check: right or wrong | Check: accuracy, quality, consistency, bias, toxicity... |

Now let's look at the differences between MLOps and LLMOps:

| features | MLOps | LLMOps |
| :---: |:----:| :----: |
| Scope | Full ML model lifecycle | Full LLM application lifecycle |
| Focus | Data preparation, model training, model deployment, model monitoring, model retraining | Data preparation, model deployment, monitoring, observability, security |
| Tools | MLOps platforms, data-preparation tools, model-training frameworks, model-deployment tools, monitoring tools | LLMOps platforms, data-preparation tools, model-deployment tools, monitoring tools, observability tools, security tools |

![alt text](<../../../02-第二章-部署与推理/assest/DevOps, AIOps, MLOps, LLMOps，这些Ops都是什么？/05.png>)

> Note: LLMOps usually means operations for large-model applications, not training large models, because training large models is an offline process, while applying large models is an online process.

## References

<div id="refer-anchor-1"></div>

[1] [What is CI/CD?](https://www.mabl.com/blog/what-is-cicd)

[2] [What is DevOps and where is it applied?](https://shalb.com/blog/what-is-devops-and-where-is-it-applied/)

[3] [What is AIOps and What are Top 10 AIOps Use Cases](https://cloudfabrix.com/blog/what-is-aiops-top-10-common-use-cases/)

[4] [MLOps](https://www.databricks.com/glossary/mlops)

[5] [LLMOps: What Is It and How To Implement Best Practices](https://spotintelligence.com/2024/01/08/llmops/)

[6] [deeplearning.ai](https://www.deeplearning.ai/short-courses/automated-testing-llmops/)

## Welcome to my GitHub and WeChat Official Account: no time to explain, hurry aboard!

[GitHub: LLMForEverybody](https://github.com/luhengshiwo/LLMForEverybody)

The repository has the original Markdown files, and it is fully open source. Stars and forks are very welcome.


---

## 📚 相关概念

[[concepts/LLM 推理 优化|LLM 推理 优化]] | [[concepts/推测解码|推测解码]] | [[concepts/分布式推理|分布式推理]] | [[concepts/模型 压缩 蒸馏|模型 压缩 蒸馏]] | [[concepts/LLM 应用 生态|LLM 应用 生态]] | [[entities/vllm|vllm]] | [[entities/tensorrt-llm|tensorrt-llm]] | [[entities/sglang|sglang]] | [[entities/Hugging Face|Hugging Face]] | [[concepts/LLM 推理 优化|LLM 推理 优化]]

> 📌 来源：[[sources/LLMForEverybody/索引|LLMForEverybody 导航]] · 章节：部署与推理
