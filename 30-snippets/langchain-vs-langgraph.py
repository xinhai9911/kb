"""
LangChain vs LangGraph 最小对比示例 (离线运行, 无需 API key)

对照:
  - LangChain : 线性链   prompt | llm | parser, 无状态无分支
  - LangGraph : 有向图   节点 + 条件边, 状态显式共享, 可循环
"""
from typing import TypedDict, Literal

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph


class MockLLM:
    """离线的模拟 LLM, 便于不配 API key 也能跑通流程."""

    def invoke(self, messages, **kwargs):
        text = messages[-1].content
        return f"[MockLLM] 简洁回答: {text}"


llm = MockLLM()


def q1_chain(question: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是中文助手，回答要简洁"),
        ("human", "{question}"),
    ])
    return (prompt | llm | StrOutputParser()).invoke({"question": question})


# ---------------- LangGraph ----------------
class State(TypedDict):
    question: str
    answer: str
    needs_followup: bool


def answer_node(state: State) -> dict:
    needs = len(state["question"]) > 20
    return {
        "answer": f"[Node answer] 简洁回答: {state['question']}",
        "needs_followup": needs,
    }


def detail_node(state: State) -> dict:
    return {"answer": state["answer"] + " (补充说明: 由 detail 节点追加)"}


def route(state: State) -> Literal["detail", "end"]:
    return "detail" if state["needs_followup"] else "end"


def build_graph():
    g = StateGraph(State)
    g.add_node("answer", answer_node)
    g.add_node("detail", detail_node)
    g.set_entry_point("answer")
    g.add_conditional_edges("answer", route, {"detail": "detail", "end": END})
    g.add_edge("detail", END)
    return g.compile()


def main():
    print("=" * 60)
    print("1) LangChain 线性链")
    print("=" * 60)
    print(q1_chain("什么是LangChain?"))
    print()

    print("=" * 60)
    print("2) LangGraph 有向图")
    print("=" * 60)
    app = build_graph()
    for q in [
        "什么是LangGraph?",                              # 短 → 走 end
        "什么是LangChain和LangGraph的区别以及各自的适用场景？",  # 长 → 走 detail
    ]:
        out = app.invoke({"question": q})
        print(f"[问题] {q}")
        print(f"[needs_followup] {out['needs_followup']}")
        print(f"[回答] {out['answer']}")
        print()


if __name__ == "__main__":
    main()
