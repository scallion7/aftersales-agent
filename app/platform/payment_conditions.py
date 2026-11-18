"""Match explicitly stated payment states to the action and charge they qualify."""

import re
from dataclasses import dataclass

# Ordered alternatives consume negation and specific states before their
# substrings (e.g. partially paid is neither fully paid nor wholly unpaid).
_PREFIX = r"(?:已经|已|刚)?(?:仅|只(?:是)?|才)?"
_PAY = r"(?:支付|付|缴纳|缴|交)"
_FULL = r"(?:全部|全额|全都|全数|完全)?(?:付清|结清|付完|交清|缴清)"
_STATE = re.compile(
    "|".join(
        f"(?P<{name}>{pattern})"
        for name, pattern in (
            (
                "negated",
                r"(?:并非|不是|不再是|并不是|还不是)(?:处于|显示)?(?:待结算|待清算|结算中|已到账|已结清|已撤回|支付失败)",
            ),
            (
                "reversal_pending",
                r"(?:撤回|撤销)(?:交易)?申请(?:尚|仍|还)?(?:在|待|正在|等待)(?:审批|审核|处理)",
            ),
            (
                "reversed",
                r"(?:交易|付款|支付)?(?:已经|已)?(?:成功(?:撤回|撤销)|(?:撤回|撤销)(?:已)?成功)",
            ),
            ("failed", r"(?:交易|付款|支付|扣款)?(?:已经|已)?失败"),
            ("pending", r"(?:待(?:结算|清算)|(?:结算|清算)中|等待清算(?!结果))"),
            (
                "partial",
                rf"{_PREFIX}(?:{_PAY}(?:了)?(?:一部分|部分|一半)|(?:部分|分批)(?:支付|付款|已付|到账))",
            ),
            ("outstanding", rf"(?:尚未|还没(?:有)?|未|没(?:有)?)\s*{_FULL}"),
            ("settled", rf"{_PREFIX}{_FULL}(?:并且|并已|且已|且|并|已经|已)?到账"),
            ("unposted", r"(?:还|仍)?(?:尚未|未|没有|没)到账"),
            ("paid", rf"{_PREFIX}{_FULL}"),
            ("unpaid", rf"(?:一分钱|一分(?:钱)?)(?:也|都)?(?:还)?(?:没|未){_PAY}"),
        )
    )
)
# A change marker establishes ordering. Two states joined by “or”, or states
# attached to different charges, never become an implicit latest status.
_CHANGE = re.compile(r"随后|后来|之后(?:又)?|而现在|但现在|现已|改为|变(?:成|为)|转为")
_CHARGE = re.compile(
    r"尾款|余款|定金|订金|运费|会员费|服务费|手续费|仓储费|积分|优惠券"
)
_CHARGE_GROUP = {"余款": "尾款", "订金": "定金"}
_ACTIONS = {
    "debit": re.compile(
        r"(?:自动|自行|主动|再次|重复|重新|再|补){0,3}(?:扣(?:款|钱|费|除)?|划扣)"
    ),
    "verify": re.compile(r"核对|核实|复核"),
    "clearing_result": re.compile(r"(?:清算|结算)(?:结果|回执)"),
    "repay": re.compile(r"(?:重新|再次)(?:付款|支付|缴纳|交款)"),
    "reminder": re.compile(
        r"(?:催缴|催付|催款)(?:通知|提醒)?|催(?:我|用户|买家)?(?:补交|缴纳|补付|支付|交|付)"
    ),
}
_LOCATION = re.compile(r"哪(?:里|儿|个页面)|什么页面")
_PAGES = re.compile(r"(?:订单|支付|活动|商品)(?:详情)?页(?:面)?")
# Recognized roles, location and the monetary subject remain distinguishable.
# Unknown content words are retained in both directions, including additional
# eligibility conditions, fees, quantities and timing questions.
_NORMAL = (
    (re.compile(r"预售(?:订单)?"), " 预售 "),
    (re.compile(r"尚欠的|余下的|剩余的?|剩下(?:的)?(?:那笔)?"), " "),
    (re.compile(r"工作人员|客服人员|客服人工|人工客服"), " 客服 "),
    (re.compile(r"是不是|会不会|是否|会否|会吗|需不需要"), " "),
    (re.compile(r"返回|等待|发出|发送|推送"), " "),
)
_GRAMMAR = frozenset(
    "我 我们 的 地 得 了 也 呢 吗 这 这笔 这单 那 那笔 笔 在 时 期间 后 然后 先 是 为 处于 "
    "显示 状态 付款 支付 交易 订单 系统 平台 买家 用户 需要 应该 应 须 要 会 将 是否 "
    "不会 不再 不 不会再 不用 禁止 已 已经 全 全部 仍 还 再 并 由 从 等 发 里 对 付 已到".split()
)


def _charge_groups(text):
    return frozenset(_CHARGE_GROUP.get(x, x) for x in _CHARGE.findall(text))


def _state_and_remainder(text, *, allow_change=True):
    matches = list(_STATE.finditer(text))
    if not matches:
        generic = _BASIC_STATE.search(text)
        if generic and generic.lastgroup == "paid":
            return "paid", text[: generic.start()] + " " + text[generic.end() :]
        return "", text
    states = {match.lastgroup for match in matches}
    if len(states) == 1:
        return matches[-1].lastgroup, _STATE.sub(" ", text)
    latest = matches[-1]
    between = text[matches[-2].end() : latest.start()]
    if (
        allow_change
        and len(_charge_groups(text)) <= 1
        and _CHANGE.search(between)
        and not any(
            pattern.search(_STATE.sub(" ", text[: latest.start()]))
            for pattern in _ACTIONS.values()
        )
    ):
        # Previous status is historical. The whole question still supplies the
        # charge, and the remainder keeps words outside the status expressions.
        return latest.lastgroup, _CHANGE.sub(" ", _STATE.sub(" ", text))
    return "ambiguous", text


# Corrections replace exactly one stated condition. These broad paid/unpaid
# forms preserve legacy wording without treating them as new detailed policies.
_BASIC_STATE = re.compile(
    r"(?P<unpaid>(?:还|仍)?(?:尚未|未|没(?:有)?)(?:来得及)?(?:补交|补缴|缴清|支付|付款|付清|付|缴纳|缴|交清|交))"
    r"|(?P<paid>(?:已经|已)(?:支付|付款|交款|付|缴款|交))"
)


def _single_state_match(text):
    if len(_charge_groups(text)) > 1:
        return None
    detailed = list(_STATE.finditer(text))
    if len(detailed) > 1:
        return None
    # Do not also count a broad expression contained in a specific one.
    all_matches = detailed + [
        generic
        for generic in _BASIC_STATE.finditer(text)
        if not any(
            generic.start() < m.end() and generic.end() > m.start() for m in detailed
        )
    ]
    if len(all_matches) != 1:
        return None
    match = all_matches[0]
    if match.lastgroup == "negated" or re.search(
        r"并非|(?:还|并)?不是|不再是|未能|没能",
        text[max(0, match.start() - 4) : match.start()],
    ):
        return None
    return match


def parse_payment_state(text):
    """Return a single unambiguous status for a conversational correction."""
    match = _single_state_match(text)
    return match.lastgroup if match else None


def replace_payment_state(text, replacement):
    """Replace one status span, preserving the rest of the original question."""
    match = _single_state_match(text)
    new = _single_state_match(replacement)
    if not match or not new:
        return None
    old_charges, new_charges = _charge_groups(text), _charge_groups(replacement)
    if old_charges and new_charges and old_charges != new_charges:
        return None
    return text[: match.start()] + new.group() + text[match.end() :]


def _words(text):
    import jieba

    return frozenset(
        word.lower()
        for word in jieba.cut(text, HMM=False)
        if re.search(r"\w", word) and word not in _GRAMMAR
    )


_ROLES = {
    "platform": re.compile(r"系统|平台"),
    "human": re.compile(r"人工|客服|工作人员"),
    "buyer": re.compile(r"买家|用户|顾客|消费者"),
}
_PREREQUISITE = re.compile(
    r"仅当|只有|须先|需先|若|如果|(?:核对|核实|复核)(?:通过|完成)?(?:后|时)"
)


@dataclass(frozen=True)
class _Part:
    actions: frozenset[str]
    terms: frozenset[str]
    pages: frozenset[str]
    owner: frozenset[str]
    prerequisite: bool

    @classmethod
    def parse(cls, text):
        actions = frozenset(
            key for key, pattern in _ACTIONS.items() if pattern.search(text)
        )
        pages = frozenset(_PAGES.findall(text))
        # Only an actor preceding the predicate can own its debit. The recipient
        # of a reminder and the owner of a bank account need not be its sender.
        predicate = next(
            (
                m
                for p in (_ACTIONS["debit"], _ACTIONS["repay"])
                if (m := p.search(text))
            ),
            None,
        )
        owner = frozenset(
            key
            for key, pattern in _ROLES.items()
            if predicate and pattern.search(text[: predicate.start()])
        )
        clean = text
        for pattern, replacement in _NORMAL:
            clean = pattern.sub(replacement, clean)
        clean = _LOCATION.sub(" ", _PAGES.sub(" ", _CHARGE.sub(" ", clean)))
        for pattern in _ACTIONS.values():
            clean = pattern.sub(" ", clean)
        return cls(
            actions, _words(clean), pages, owner, bool(_PREREQUISITE.search(text))
        )


@dataclass(frozen=True)
class PaymentCondition:
    state: str
    charges: frozenset[str]
    parts: tuple[_Part, ...]
    location: bool

    @property
    def actions(self):
        return frozenset().union(*(part.actions for part in self.parts))

    @property
    def terms(self):
        return frozenset().union(*(part.terms for part in self.parts))

    @classmethod
    def parse(cls, text, *, allow_change=True):
        state, remainder = _state_and_remainder(text, allow_change=allow_change)
        if not state:
            return None
        parts = tuple(_Part.parse(part) for part in re.split(r"[，,]", remainder))
        return cls(
            state, _charge_groups(text), parts, bool(_LOCATION.search(remainder))
        )

    def check(self, clause):
        source = self.parse(clause, allow_change=False)
        if not source or self.state in {"negated", "ambiguous"}:
            return "payment_condition_missing"
        if self.state != source.state and not (
            self.state == "settled" and source.state == "paid"
        ):
            return "payment_condition_mismatch"
        if len(self.charges) != 1 or self.charges != source.charges:
            return "payment_object_mismatch"
        actions = self.actions
        if not actions or not actions.issubset(source.actions):
            return "payment_action_missing"
        applicable = [
            part
            for part in source.parts
            if not part.actions or part.prerequisite or part.actions & actions
        ]
        if any(part.prerequisite and part.actions - actions for part in applicable):
            return "additional_payment_condition"
        pages = frozenset().union(
            *(part.pages for part in applicable if part.actions & actions)
        )
        if any(part.pages - pages for part in self.parts):
            return "payment_location_mismatch"
        for query in self.parts:
            if not query.actions:
                continue
            matching = [part for part in applicable if query.actions <= part.actions]
            if not any(
                query.pages <= part.pages
                and (not self.location or part.pages)
                and (not query.owner or query.owner <= (part.owner or {"platform"}))
                for part in matching
            ):
                return "payment_action_scope_mismatch"
        relevant = frozenset().union(*(part.terms for part in applicable))
        if self.terms - relevant:
            return "query_subject_or_condition_missing"
        if relevant - self.terms:
            return "additional_payment_condition"
        return "supported"
