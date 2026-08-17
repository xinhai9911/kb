import os, re

# ---------------- dictionary (same as preview) ----------------
PROPER_MAP = {
    "llm":"LLM","llms":"LLM","ai":"AI","agi":"AGI","nlp":"NLP","es":"ES",
    "elk":"ELK","kibana":"Kibana","hbase":"HBase","influxdb":"InfluxDB",
    "hive":"Hive","fpga":"FPGA","axi4":"AXI4","axi":"AXI","ddr":"DDR",
    "uart":"UART","spi":"SPI","i2c":"I2C","rtl":"RTL","zynq":"Zynq",
    "riscv":"RISC-V","soc":"SoC","xdc":"XDC","sdc":"SDC","ip":"IP",
    "vpp":"VPP","npp":"NPP","dpdk":"DPDK","gpu":"GPU","dpu":"DPU","nic":"NIC",
    "nvme":"NVMe","ssd":"SSD","serdes":"SerDes","phy":"PHY","asic":"ASIC",
    "obsidian":"Obsidian","ida":"IDA","clip":"CLIP","vllm":"vLLM","tgi":"TGI",
    "tensorrt":"TensorRT","ollama":"Ollama","llama":"LLaMA","deepseek":"DeepSeek",
    "huggingface":"HuggingFace","crewai":"CrewAI","langchain":"LangChain",
    "coze":"Coze","kubernetes":"Kubernetes","mcp":"MCP","rag":"RAG",
    "graphrag":"GraphRAG","mla":"MLA","lora":"LoRA","peft":"PEFT","qlora":"QLoRA",
    "adalora":"AdaLoRA","moe":"MoE","rlhf":"RLHF","dpo":"DPO",
    "flashattention":"FlashAttention","swiglu":"SwiGLU","megatron":"Megatron",
    "deepspeed":"DeepSpeed","fsdp":"FSDP","accelerate":"Accelerate",
    "transformer":"Transformer","transformers":"Transformer","attention":"Attention",
    "rope":"RoPE","bpe":"BPE","wordpiece":"WordPiece","unigram":"Unigram",
    "sentencepiece":"SentencePiece","bbpe":"BBPE","mamba":"Mamba",
    "pagedattention":"PagedAttention","devops":"DevOps","aiops":"AIOps",
    "mlops":"MLOps","llmops":"LLMOps","jira":"Jira","zentao":"禅道",
    "turnitin":"Turnitin","google":"Google","adk":"ADK","openai":"OpenAI",
    "anthropic":"Anthropic","amd":"AMD","epyc":"EPYC","intel":"Intel",
    "centec":"Centec","motorcomm":"Motorcomm","tap":"TAP","nsf":"NSF",
    "smartnic":"SmartNIC","davinci":"DaVinci","resolve":"Resolve",
    "adobe":"Adobe","premiere":"Premiere","final":"Final","capcut":"CapCut",
    "excalidraw":"Excalidraw","paas":"PaaS","eda":"EDA","chatbi":"ChatBI",
    "crud":"CRUD","etl":"ETL","sql":"SQL","db":"DB","ctc":"CTC","cot":"CoT",
    "tot":"ToT","got":"GoT","sgd":"SGD","adam":"Adam","adamw":"AdamW",
    "radam":"RAdam","nadam":"NAdam","rmsprop":"RMSProp","adagrad":"AdaGrad",
    "adadelta":"AdaDelta","asgd":"ASGD","rprop":"RProp","batchnorm":"BatchNorm",
    "layernorm":"LayerNorm","relu":"ReLU","gelu":"GELU","selu":"SeLU","elu":"ELU",
    "swish":"Swish","mish":"Mish","sigmoid":"Sigmoid","softmax":"Softmax",
    "tanh":"Tanh","glu":"GLU","pmbok":"PMBOK","scrum":"Scrum","kanban":"看板",
    "xp":"XP","kpi":"KPI","hcna":"HCNA","hcnp":"HCNP","api":"API","sdk":"SDK",
    "pro":"Pro","avid":"Avid","nle":"NLE","adr":"ADR","dit":"DIT","qc":"QC",
    "hdr":"HDR","studiobinder":"StudioBinder","factory":"Factory",
    "elasticsearch":"Elasticsearch","claude":"Claude","hugging":"Hugging","face":"Face",
}
WORD = {
    "framework":"框架","frameworks":"框架","agent":"智能体","agents":"智能体",
    "agentic":"智能体","neural":"神经","network":"网络","networks":"网络",
    "training":"训练","fine":"微调","finetuning":"微调","tuning":"调优",
    "inference":"推理","serving":"服务部署","optimizers":"优化器","optimizer":"优化器",
    "optimization":"优化","optimize":"优化","memory":"内存","parallelism":"并行",
    "distributed":"分布式","scratch":"从零","tokenizers":"分词器","tokenizer":"分词器",
    "tokens":"词元","token":"词元","activation":"激活","prompt":"提示词",
    "prompts":"提示词","prompting":"提示工程","embedding":"嵌入","embeddings":"嵌入",
    "vector":"向量","retrieval":"检索","generation":"生成","retrieve":"检索",
    "multimodal":"多模态","multi":"多","alignment":"对齐","evaluation":"评估",
    "evaluate":"评估","benchmarks":"基准","benchmark":"基准","latency":"延迟",
    "throughput":"吞吐","ttft":"首字延迟","performance":"性能","perf":"性能",
    "engineering":"工程","production":"制作","deployment":"部署","deploy":"部署",
    "pipeline":"流水线","workflow":"工作流","adapter":"适配器","adapters":"适配器",
    "engine":"引擎","architecture":"架构","architect":"架构师","overview":"概览",
    "intro":"入门","introduction":"入门","guide":"指南","usage":"用法","use":"使用",
    "how":"如何","what":"什么","why":"为什么","index":"索引","glossary":"术语表",
    "template":"模板","templates":"模板","best":"最佳","practices":"实践",
    "practice":"实践","part":"部分","patterns":"模式","pattern":"模式",
    "techniques":"技巧","technique":"技巧","methods":"方法","method":"方法",
    "theory":"理论","analysis":"分析","design":"设计","decoder":"解码器",
    "test":"测试","tests":"测试","plan":"计划","execution":"执行","report":"报告",
    "plugin":"插件","plugins":"插件","dev":"开发","system":"系统","protocol":"协议",
    "management":"管理","comparison":"对比","application":"应用","applications":"应用",
    "hybrid":"混合","ecosystem":"生态","advanced":"进阶","adoption":"落地",
    "basic":"基础","basics":"基础","concepts":"概念","concept":"概念",
    "essential":"要点","essentials":"要点","quick":"快速","fast":"快速","deep":"深入",
    "internals":"原理","principles":"原则","principle":"原则","selection":"选择",
    "monitoring":"监控","lightweight":"轻量","evolution":"演进","future":"未来",
    "mastery":"精通","masterclass":"大师课","notes":"笔记","examples":"示例",
    "example":"示例","case":"案例","explained":"详解","understand":"理解",
    "understanding":"理解","explore":"探索","exploration":"探索","dive":"深入",
    "complete":"完整","common":"常见","classical":"经典","classic":"经典",
    "practical":"实用","reference":"参考","references":"参考","book":"书籍",
    "books":"书籍","paper":"论文","papers":"论文","research":"研究",
    "studies":"研究","study":"研究","survey":"综述","search":"搜索","storage":"存储",
    "database":"数据库","databases":"数据库","data":"数据","knowledge":"知识",
    "enterprise":"企业","structured":"结构化","graph":"图","semantic":"语义",
    "fusion":"融合","mesh":"网格","augmented":"增强","local":"本地","long":"长",
    "short":"短","low":"低","high":"高","cost":"成本","scaling":"扩展","scale":"扩展",
    "metrics":"指标","metric":"指标","service":"服务","offline":"离线","online":"在线",
    "split":"拆分","private":"私有","security":"安全","attack":"攻击","attacks":"攻击",
    "jailbreak":"越狱","safety":"安全","classification":"分类","rank":"秩",
    "ranking":"排序","echelon":"分解","basis":"基","matrix":"矩阵","matrices":"矩阵",
    "vectors":"向量","eigenvalues":"特征值","eigenvectors":"特征向量",
    "bayes":"贝叶斯","distributions":"分布","distribution":"分布","probability":"概率",
    "statistics":"统计","statistic":"统计","formula":"公式","formulas":"公式",
    "derivative":"导数","gradient":"梯度","descent":"下降","central":"中心",
    "limit":"极限","theorem":"定理","calculus":"微积分","singularity":"奇异",
    "reduction":"归约","algebra":"代数","linear":"线性","nonlinear":"非线性",
    "transformations":"变换","transformation":"变换","functions":"函数",
    "function":"函数","positional":"位置","encoding":"编码","eulers":"欧拉",
    "math":"数学","mathematics":"数学","complex":"复","complexity":"复杂度",
    "variants":"变体","implementation":"实现","implement":"实现","specification":"规范",
    "spec":"规范","technical":"技术","landscape":"全景","build":"构建","develop":"开发",
    "developing":"开发","building":"构建","code":"代码","coding":"编程",
    "orchestration":"编排","tool":"工具","tools":"工具","model":"模型","models":"模型",
    "distillation":"蒸馏","browser":"浏览器","self":"自","human":"人类",
    "emergence":"涌现","origin":"起源","intelligence":"智能","law":"定律","ops":"运维",
    "mean":"含义","speed":"速度","following":"跟随","difference":"区别","vs":"对比",
    "grouped":"分组","instead":"替代","appeared":"出现","changed":"改变","most":"最",
    "beautiful":"优美","mathematical":"数学","earlier":"早期","factors":"因素",
    "compute":"计算","communication":"通信","problem":"问题","problems":"问题",
    "new":"新","profession":"职业","professions":"职业","counting":"计数",
    "stars":"星","have":"有","protection":"保护","choosing":"选择","eat":"吃",
    "passed":"通过","exam":"考试","describing":"描述","article":"文章","tensor":"张量",
    "experts":"专家","mixture":"混合","excerpt":"摘录","needle":"针",
    "haystack":"大海","nth":"第N","room":"房间","exploit":"漏洞利用","challenge":"挑战",
    "challenges":"挑战","chain":"链","tree":"树","thought":"思考","paradigms":"范式",
    "paradigm":"范式","over":"在","left":"左","right":"右","end":"端",
    "engineer":"工程师","repeater":"复述","hallucinations":"幻觉","uncertainty":"不确定性",
    "uncertain":"不确定","past":"过去","tense":"时态","can":"能","scene":"场景",
    "lighting":"灯光","color":"调色","colour":"调色","grading":"调色","grade":"调色",
    "grades":"调色","colorist":"调色师","editor":"剪辑师","editing":"剪辑",
    "edits":"剪辑","cut":"剪辑","cuts":"剪辑","montage":"蒙太奇","storyboard":"分镜",
    "shot":"镜头","shots":"镜头","sizing":"尺寸","axes":"轴线","camera":"摄影机",
    "sound":"声音","music":"音乐","post":"后期","vfx":"视觉特效","motion":"运动",
    "graphics":"图形","documentary":"纪录片","genre":"类型","script":"剧本",
    "dp":"摄影指导","department":"部门","set":"片场","movements":"运动","angle":"角度",
    "composition":"构图","industry":"行业","role":"角色","history":"历史",
    "famous":"著名","festival":"电影节","distribution":"发行","tips":"技巧",
    "performance":"表演","adaptation":"改编","archive":"归档","strategy":"策略",
    "repair":"修复","looks":"影调","titling":"字幕","localization":"本地化",
    "specs":"规格","compatibility":"兼容性","career":"职业","path":"路径",
    "business":"商业","legal":"法务","lens":"镜头","decisions":"决策","standards":"标准",
    "staging":"走位","blocking":"走位","rehearsal":"排练","tv":"电视","series":"剧集",
    "animation":"动画","experimental":"实验","cinema":"电影",
    "signatures":"签名","matchmove":"匹配移动","science":"科学","gamut":"色域",
    "dubbing":"配音","sports":"体育","methodologies":"方法论","methodology":"方法论",
    "agile":"敏捷","risk":"风险","requirements":"需求","requirement":"需求",
    "schedule":"进度","quality":"质量","stakeholder":"干系人","estimation":"估算",
    "estimate":"估算","estimates":"估算","change":"变更","configuration":"配置",
    "documentation":"文档","lean":"精益","team":"团队","teaming":"协作",
    "collaboration":"协作","planning":"规划","chinese":"中文","translation":"翻译",
    "readme":"README","log":"日志","hot":"热点","tag":"标签","sources":"来源",
    "snippets":"片段","callout":"标注","conventions":"规范","markdown":"Markdown",
    "kb":"知识库","zero":"零","hero":"入门","reverse":"逆向","inaction":"实战",
    "server":"服务端","bigdata":"大数据","mastering":"精通","tech":"技术",
    "hardware":"硬件","misc":"杂项","accelerator":"加速器","domestic":"国产",
    "flow":"流","track":"轨道","actors":"演员","approaches":"方法","mezzanine":"夹层",
    "proxy":"代理","transitions":"转场","multicam":"多机位","chroma":"色度",
    "key":"键","compositing":"合成","efficiency":"效率","raw":"RAW","formats":"格式",
    "format":"格式","delivery":"交付","audio":"音频","psychology":"心理学",
    "narrative":"叙事","nonlinear":"非线性","director":"导演","directing":"导演",
    "directors":"导演","film":"电影","filmmaking":"电影制作","three":"三","act":"幕",
    "structure":"结构","mise":"场面","en":"在","technology":"技术",
    "drop":"删除","table":"表","packet":"包","static":"静态","bus":"总线",
    "constraints":"约束","catalog":"目录","timer":"定时器","mechanism":"机制",
    "cleanup":"清理","verification":"验证","device":"设备","codec":"编解码器",
    "l-cut":"L切","j-cut":"J切","explained":"详解","building":"构建","landscape":"全景",
    "systematic":"系统性","pre":"预","libretexts":"教材","bang":"爆款","write":"写作",
    "larry":"拉里","jordan":"乔丹","mpegflow":"MPEGFlow","forte":"强项","cognition":"认知",
    "plos":"PLOS","cinapex":"CinApex","references":"参考","ru":"俄","en":"英",
    "snippets":"片段","video":"视频","switch":"交换机","chips":"芯片","chip":"芯片",
    "controller":"控制器","compression":"压缩","budget":"预算","grammar":"文法",
    "versioning":"版本管理","power":"强力","panorama":"全景","genai":"生成式AI",
    "skeleton":"骨架","harness":"测试框架","determinant":"行列式","row":"行",
    "red":"红队","text":"文本","one":"一","first":"首","input":"输入","cheap":"廉价",
    "easy":"简易","minutes":"分钟","unlocking":"解锁","pm":"项目管理",
    "matanaliz":"数学分析","matematika":"数学","lineynaya":"线性","algebra":"代数",
    "veroyatnost":"概率","statistika":"统计","slozhnost":"复杂度","vnedreniya":"应用",
    "prilozheniya":"应用","prilozheniyah":"应用","arhitekturnoe":"架构",
    "principy":"原则","dannym":"数据","vybora":"选择","ranee":"早期",
    "dlya":"用于","nulya":"从零","chast":"部分","tehnologii":"技术",
    "ispylzovat":"使用","vyvod":"输出","vyvoda":"推理","povtorov":"重复",
    "problema":"问题","inzhenera":"工程师","ekzamen":"考试","sistemnogo":"系统",
    "arhitektora":"架构师","vtoroy":"第二","polovine":"半","povtorenie":"复习",
    "cherez":"通过","zaschita":"保护","matricy":"矩阵","vektory":"向量",
    "lineynye":"线性","preobrazovaniya":"变换","proizvodnaya":"导数",
    "gradientnyy":"梯度","spusk":"下降","opisanie":"描述","centralnaya":"中心",
    "predelnaya":"极限","glavnoe":"主","pole":"场","bitvy":"战场",
    "imitatora":"模仿者","vladelcu":"所有者","platformy":"平台","professiya":"职业",
    "novaya":"新","zvezd":"星","podscheta":"计算","zadacha":"任务","metriki":"指标",
    "kakie":"哪些","mozhno":"可","bolshoy":"大","tekst":"文本","raskryvaem":"揭示",
    "silu":"潜力","poisk":"搜索","narrativnym":"叙事","privatnym":"私有",
    "proektirovat":"设计","arhitekturu":"架构","nalevo":"左","napravo":"右",
    "proektirovanie":"设计","klassifikaciya":"分类","bazovye":"基础",
    "ponyatiya":"概念","bystryy":"快速","vnutrennie":"内部","minut":"分钟",
    "paradigmy":"范式","proektirovaniya":"设计","populyarnye":"流行",
    "freymvorki":"框架","prakticheskoe":"实用","rukovodstvo":"指南",
    "razrabatyvat":"开发","vektornye":"向量","bazy":"库","dannyh":"数据",
    "arhitektura":"架构","protiv":"对抗","problemy":"问题","edy":"食","sdal":"通过",
    "ocenka":"评估","vzlomat":"破解","est":"是","konets":"端",
}
WORD.update({
    "flowtable":"流表","proshedshim":"过去","vremenem":"时间","bezopasnost":"安全",
    "ataki":"攻击","ispolzovat":"使用","raspredeleniy":"分布","raspredeleniya":"分布",
    "strukturirovannyy":"结构化","neopredelennost":"不确定性","gallyucinacii":"幻觉",
    "teorema":"定理","start":"启动","main":"主","battlefield":"战场","imitator":"模仿者",
    "platform":"平台","term":"期","levels":"层级","needed":"所需","large":"大",
    "language":"语言","query":"查询","easiest":"最简单","way":"方式","other":"其他",
    "parameter":"参数","efficient":"高效","quantization":"量化","algorithms":"算法",
    "output":"输出","mean":"含义","repo":"仓库","you":"你","tube":"视频","fix":"修复",
    "spelling":"拼写","translate":"翻译","summarize":"摘要","simplify":"简化",
    "emojify":"表情化","make":"生成","shorter":"更短","longer":"更长","remove":"移除",
    "urls":"URL","rewrite":"改写","tweet":"推文","thread":"线程","web":"网页",
    "page":"页面","resume":"简历","card":"卡","education":"教育","gaokao":"高考",
    "job":"工作","ali":"阿里","bytedance":"字节","marriage":"婚姻","house":"房",
    "startup":"创业","divorce":"离婚","illness":"病","progress":"进度","task":"任务",
    "brief":"简报","designer":"设计师","ironhive":"IronHive","opencloudos":"OpenCloudOS",
    "h3c":"H3C","qkb":"QKB","vaswani":"Vaswani","davinci":"DaVinci","apple":"Apple",
    "strategies":"策略","vendors":"厂商","summit":"峰会","privacy":"隐私",
    "explain":"解释","generate":"生成","transcript":"转录","today":"今天","now":"现在",
    "ocenki":"评估","media":"媒体","composer":"合成器","auteur":"作者论",
})
FILLER = {
    "to","and","in","of","for","from","with","a","the","an","on","as","or","is",
    "at","by","that","this","into","about","per","do","whats","these","than","more",
    "like","am","s","p","v","h","c","j","l","k","ot","vo","u","ya","po","za","kak",
    "ili","li","est","i",
}

def translate_segment(seg):
    sub = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]|[0-9]+', seg)
    if not sub:
        sub = [seg]
    out = []
    for s in sub:
        key = s.lower()
        if key in PROPER_MAP:
            out.append(PROPER_MAP[key]); continue
        if key in FILLER:
            continue
        if key in WORD:
            out.append(WORD[key]); continue
        out.append(s)
    return " ".join(out).strip()

def to_chinese_name(base):
    segs = re.split(r'[-_]+', base)
    parts = [translate_segment(s) for s in segs if s]
    return " ".join(p for p in parts if p).strip()

# ---------------- rename + rewrite ----------------
SKIP = ['.git', '.obsidian', '.venv', 'node_modules']

def collect_md():
    files = []
    for dp, dn, fn in os.walk('.'):
        if any(s in dp for s in SKIP): continue
        for f in fn:
            if f.lower().endswith('.md'):
                files.append(os.path.join(dp, f))
    return files

def ascii_only(b):
    return all(ord(c) < 128 for c in b)

def plan_renames(all_md):
    plan = []
    dir_used = {}
    for path in all_md:
        base = os.path.splitext(os.path.basename(path))[0]
        if not ascii_only(base):
            continue
        new = to_chinese_name(base)
        if not new or new == base:
            continue
        d = os.path.dirname(path)
        ext = os.path.splitext(path)[1]
        taken = dir_used.setdefault(d, set())
        cand = new
        i = 2
        while cand in taken or os.path.exists(os.path.join(d, cand + ext)):
            cand = f"{new} {i}"
            i += 1
        taken.add(cand)
        plan.append((path, os.path.join(d, cand + ext), base, cand))
    return plan

def add_alias(content, old_base):
    q = old_base.replace('\\', '\\\\').replace('"', '\\"')
    if content.startswith('---'):
        lines = content.split('\n')
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end = i; break
        if end is None:
            return f'---\naliases: ["{q}"]\n---\n\n' + content
        for i in range(1, end):
            if lines[i].strip().startswith('aliases'):
                return content  # already has aliases; skip to avoid corrupting
        lines.insert(1, f'aliases: ["{q}"]')
        return '\n'.join(lines)
    return f'---\naliases: ["{q}"]\n---\n\n' + content

WIKILINK = re.compile(r'\[\[([^\]\n]+?)\]\]')
MDLINK = re.compile(r'\]\(([^)\n]+\.md)\)')

def rewrite_text(text, old2new):
    out = []
    fence = False
    for line in text.split('\n'):
        if line.lstrip().startswith('```') or line.lstrip().startswith('~~~'):
            fence = not fence
            out.append(line); continue
        if fence:
            out.append(line); continue
        def rw(m):
            inner = m.group(1)
            target, alias = inner.split('|', 1) if '|' in inner else (inner, None)
            head = None
            if '#' in target:
                target, head = target.split('#', 1)
            tbase = target.split('/')[-1].strip()
            if tbase in old2new:
                prefix = target[:len(target) - len(tbase)]
                nt = prefix + old2new[tbase]
                if head is not None:
                    nt += '#' + head
                if alias is not None:
                    nt += '|' + alias
                return '[[' + nt + ']]'
            return m.group(0)
        line = WIKILINK.sub(rw, line)
        def rm(m):
            p = m.group(1)
            anchor = ''
            if '#' in p:
                p, anchor = p.split('#', 1)
            base = os.path.basename(p)
            nb = os.path.splitext(base)[0]
            if nb in old2new:
                dirpart = p[:len(p) - len(base)]
                np_ = dirpart + old2new[nb] + os.path.splitext(base)[1]
                if anchor:
                    np_ += '#' + anchor
                return '](' + np_ + ')'
            return m.group(0)
        line = MDLINK.sub(rm, line)
        out.append(line)
    return '\n'.join(out)

def main():
    all_md = collect_md()
    plan = plan_renames(all_md)
    old2new = {old: new for (_, _, old, new) in plan}
    new2old = {new: old for (_, _, old, new) in plan}
    print(f"Files to rename: {len(plan)}")
    # rename
    for oldp, newp, old, new in plan:
        os.rename(oldp, newp)
    # rewrite links + add aliases in all CURRENT md files
    cur = collect_md()
    changed_links = 0
    changed_alias = 0
    for path in cur:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            text = fh.read()
        newtext = rewrite_text(text, old2new)
        base = os.path.splitext(os.path.basename(path))[0]
        if base in new2old:
            newtext = add_alias(newtext, new2old[base])
            changed_alias += 1
        if newtext != text:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(newtext)
            changed_links += 1
    # write mapping report
    with open('_tmp_mapping.txt', 'w', encoding='utf-8') as fh:
        for oldp, newp, old, new in plan:
            fh.write(f"{old}\t->\t{new}\n")
    print(f"Link/content files updated: {changed_links}")
    print(f"Alias headers added: {changed_alias}")
    print("Mapping written to _tmp_mapping.txt")

if __name__ == "__main__":
    main()
