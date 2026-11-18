"""Match bounded retail policy questions to the subject, action and conditions of a passage."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Only broaden a named garment to a policy for clothing in general. A policy
# for one garment cannot be used for another garment or all clothing.
_CLOTHING = frozenset("服装 服饰 衣物 衣服 成衣".split())
_GARMENTS = frozenset(
    "外套 上衣 大衣 风衣 夹克 衬衣 衬衫 卫衣 毛衣 羽绒服 连衣裙 裙子 裤子 牛仔裤 T恤".split()
)
_PRODUCT = re.compile("|".join(sorted(_CLOTHING | _GARMENTS, key=len, reverse=True)))
_RETURN = re.compile(
    r"退换货?|退货|退回商品|换货|(?:能|可以|允许|还能|可不可以|申请|办理)(退|换)(?!货|换|款|钱|回)"
)
_TAG = r"(?:吊牌|商品标签)"
_REMOVED = (
    r"(?:剪(?:掉|断|下)?|拆(?:掉|下|除)?|摘(?:掉|下)?|撕(?:掉|下)?|弄丢|丢失|扔掉)"
)
_INTACT = re.compile(
    rf"{_TAG}(?:与|和)(?:{'|'.join(sorted(_CLOTHING, key=len, reverse=True))})(?:仍然|还|仍)?连(?:在一起|着)|"
    rf"(?:(?:保留(?:着)?|留着|有|带着)|(?:未|没(?:有)?){_REMOVED})(?:原装|原有)?{_TAG}"
    rf"|{_TAG}(?:仍然|一直|还|仍|是|原样)?(?:挂(?:在原处|着)|保留|留(?:在原处|着)|还在|完好(?:无损)?|完整|齐全|未{_REMOVED}|没(?:有)?{_REMOVED}|在(?:原处)?)"
)
_MISSING = re.compile(
    rf"(?:没有(?:保留)?|没(?:有)?留|未保留|{_REMOVED}(?:了)?){_TAG}"
    rf"|{_TAG}(?:已经|已|被)?(?:{_REMOVED}|不完整|不在|没了|破损)"
)
_RECEIPT = re.compile(r"签收|收货|收到(?:货)?")
_NUMBER = r"[零〇一二两三四五六七八九十百\d]+"
_ELAPSED = re.compile(
    rf"(?:第)?{_NUMBER}(?:个)?(?:天|日|周|星期|个月)(?:以内|之内|内)?|(?:上|这|本)(?:周|星期|个月)|昨天|前天"
)
_WINDOW = re.compile(
    r"退货期(?:限)?|(?:时间)?窗口|时限|期限|多久|几天|多长(?:时间)?|多少天|哪一天"
)
_UNPAID = re.compile(
    r"(?:还|仍)?(?:尚未|未|没(?:有)?)(?:来得及)?(?:补交|补缴|补|缴清|支付|付款|付清|付|缴纳|缴|交清|交)"
)
_PAID = re.compile(r"(?:已(?:经)?|已经)(?:付清|付款|支付|交清|缴清)|付清")
_LATE = re.compile(
    r"逾期|过期|到期未付|活动结束|(?:付款|支付)?(?:日期|期限|期)已过|(?:过了|错过|超过|超出)(?:付款|支付|截止)?(?:日期|时限|期限)"
)
_DEADLINE = re.compile(r"(?:尾款|付款|支付)?(?:截止日(?:期)?|期限)")
_BALANCE = re.compile(r"尾款|余款")
_PRESALE = re.compile(r"预售(?:订单|商品|单)?")
_DEPOSIT = re.compile(r"定金|订金")
_PUBLISHED = re.compile(r"标(?:出|明|注|示)|注明|公示|公布|发布")
_LOCATE = re.compile(r"(?:去|到)?哪(?:里|儿|个页面)(?:查(?:看|询)?|看)?")
_NEXT = re.compile(r"下一步|接下来")
_CARD = re.compile(r"(?:银行卡|卡里|卡中)")
_UNIVERSAL_NO_DEBIT = re.compile(
    r"不(?:会)?(?:自动|自行)(?:扣款|扣钱|扣费)[。；，,\s]*$"
)
_RETURN_DECLARATION = re.compile(
    r"(?:不可|不能|不得|不允许|不支持|允许|支持|可)(?:申请|办理)?(?=退|换)"
)
_HUMAN = re.compile(r"人工(?:介入|处理|客服)?|工作人员")
_SOURCE_SCOPE = re.compile(
    r"(?:仅限于?|(?:仅|只)?适用于?|适用范围[为：:]?|仅面向|仅(?=绑定|开通)|只有)([^，,。；;！？\n]+)"
)
_AUTOMATIC = re.compile(r"自动|自行|自己|主动|直接从|系统(?:会)?(?=扣)")
_DEBIT = re.compile(r"扣(?:款|钱|费|除)?|划(?:扣|款|走)|收款")
_DECLARED_DEBIT = re.compile(
    r"(?:不(?:会)?|不会|无需|将|会|可|须|需要|默认|由系统)?(?:自动|自行|主动|自己)(?:从(?P<account>[^，,。；;]{1,10}?))?(?:扣(?:款|钱|费|除)|划(?:扣|款|走)|收款)"
)
_EXCLUDED = re.compile(r"不适用|不包含|不包括|不涉及|除外|另行规定|以其他.*为准")
# A debit statement must finish with the debit predicate and its named
# monetary object. A mention inside an authorization, a question or a fee
# description does not establish whether the purchase balance is debited.
_DEBIT_OBJECT = re.compile(
    r"(?:本单|该笔|这笔|相应|剩余)?(?:尾款|余款|定金|订金)?[。.!！\s]*$"
)
_QUESTION_FORM = re.compile(r"是否|能否|可否|会不会|能不能|[吗么呢][。.!！\s]*$")
_SCHEDULE_REFERENCE = re.compile(
    r"(?:截止日(?:期)?|期限)(?:为|以|见|详见)(?:[\w]{1,8}页|公告|通知|合同)"
    r"(?:中|上)?(?:注明|标明|标注|标示|公示|公布|显示)(?:的)?(?:日期|时间)?"
)
_MANUAL_ACTION = re.compile(
    r"(?:必须|须|需要|需|应|请)?(?:转交|转|交给|联系|由)?人工(?:客服)?(?:处理|核实|介入)"
)
# Non-content words matter only after removing the recognised facets. Never
# discard a generic negation, a product noun or an unknown business action.
_FRAMING = frozenset(
    "我 我们 请 请问 想问 想 知道 问 一下 这个 我的 了 的 地 得 还 能 可以 会 要 吗 呢 "
    "是否 可否 能否 能不能 可不可以 可不 能不能够 还能 如何 怎么样 在 从 已经 刚 后 之后 "
    "还能不能 那么 那 如果 该 系统 平台 订单 已 上 有 提出 确认 这单 这笔 钱 仍 一直 是 还是 联系 找 需要 等 这 单 订 到 具体 最后 应 怎么办".split()
)
_RETURN_GRAMMAR = frozenset(
    "可 允许 支持 申请 办理 以内 内 之内 起 算 起算 之日起".split()
)


def _words(text):
    import jieba

    return {w.lower() for w in jieba.cut(text, HMM=False) if re.search(r"\w", w)}


def _tag_state(text):
    # A negative prefix must not be re-interpreted as positive because its
    # suffix matches "保留吊牌", or as negative because "未拆吊牌" contains "拆吊牌".
    states = [m.lastgroup for m in _TAG_STATES.finditer(text)]
    return set(states)


_TAG_STATES = re.compile(
    f"(?P<missing>{_MISSING.pattern})|(?P<intact>{_INTACT.pattern})"
)


def _return_types(text):
    kinds = set()
    for match in _RETURN.finditer(text):
        word = match.group()
        if word.startswith("退换"):
            kinds.update(("退", "换"))
        else:
            kinds.add(match[1] or word[0])
    return kinds


def _without(text, *patterns):
    for pattern in patterns:
        text = pattern.sub(" ", text)
    return text


def _within_product_scope(product, scope):
    return product == scope or (
        scope in _CLOTHING and (product in _CLOTHING or product in _GARMENTS)
    )


@dataclass(frozen=True)
class PolicyQuestion:
    kind: str
    products: frozenset[str]
    actions: frozenset[str]
    tags: frozenset[str]
    terms: frozenset[str]
    needs_window: bool
    payment_state: str = ""
    subject: frozenset[str] = frozenset()
    asks_location: bool = False

    def check(self, text, *, context=None, metadata=None):
        """Return a retrieval relevance decision; the original quote retains its polarity."""
        product = (context or {}).get("product", "")
        declared = set((metadata or {}).get("products", []))
        if product and declared and product not in declared:
            return {
                "supported": False,
                "reason": "context_product_mismatch",
                "kind": self.kind,
            }
        reasons = []
        if _EXCLUDED.search(text):
            return {"supported": False, "reason": "excluded_scope", "kind": self.kind}
        for scope in _SOURCE_SCOPE.findall(text):
            scope_words = (
                _words(re.split(r"[的](?:预售|订单|用户|顾客)", scope)[0]) - _FRAMING
            )
            if scope_words - self.terms:
                return {
                    "supported": False,
                    "reason": "unconfirmed_clause_scope",
                    "kind": self.kind,
                }
        for clause in re.findall(r"[^。！？!?；;\n]+[。！？!?；;]?", text):
            if clause.rstrip().endswith(("?", "？")):
                reasons.append("question_without_rule")
                continue
            if not clause.strip():
                continue
            reason = self._check_clause(clause, product, declared)
            if reason == "supported":
                return {
                    "supported": True,
                    "reason": reason,
                    "kind": self.kind,
                    "quote": clause,
                }
            reasons.append(reason)
        return {
            "supported": False,
            "reason": reasons[0] if reasons else "empty_clause",
            "kind": self.kind,
        }

    def _check_clause(self, clause, product, declared):
        if _QUESTION_FORM.search(clause):
            return "question_without_rule"
        if self.kind == "return":
            named_products = set(_PRODUCT.findall(clause))
            requested = self.products
            if product:
                if requested and any(
                    not (
                        _within_product_scope(p, product)
                        or _within_product_scope(product, p)
                    )
                    for p in requested
                ):
                    return "context_product_mismatch"
                # Without a product filter on the document, the passage itself
                # must connect the selected product to this return policy.
                if named_products:
                    if not any(
                        _within_product_scope(product, p) for p in named_products
                    ) and not (
                        requested
                        and any(
                            _within_product_scope(p, product) and p in named_products
                            for p in requested
                        )
                    ):
                        return "context_product_mismatch"
                elif product not in _words(clause) and product not in declared:
                    return "context_product_unverified"
                # A selected garment refines a generic question about clothes.
                if product in _GARMENTS and requested.issubset(_CLOTHING):
                    requested = {product}
            scopes = named_products or declared
            if (not product and not requested and not self.terms) or any(
                not any(_within_product_scope(p, scope) for scope in scopes)
                for p in requested
            ):
                return "product_mismatch"
            if not self.actions.issubset(_return_types(clause)):
                return "return_action_mismatch"
            if len(self.tags) != 1 or self.tags != _tag_state(clause):
                return "tag_condition_mismatch"
            if self.needs_window and not (
                _ELAPSED.search(clause) and _RECEIPT.search(clause)
            ):
                return "receipt_window_missing"
            # Keep additional restrictions in the clause. Examples include
            # wearing, washing, clearance stock, regional or channel qualifiers.
            remainder = _without(
                clause,
                _TAG_STATES,
                _PRODUCT,
                _RETURN_DECLARATION,
                _RETURN,
                _RECEIPT,
                _WINDOW,
                _ELAPSED,
            )
            extra = _words(remainder) - _FRAMING - _RETURN_GRAMMAR
            if product:
                extra.discard(product.lower())
            if product and product in declared:
                extra -= {"商品", "本品"}
            if extra - self.terms:
                return "additional_clause_condition"
        elif self.kind in {"automatic_debit", "billing_detail"}:
            if not self.subject.issubset(_billing_subject(clause)):
                return "billing_subject_mismatch"
            if self.kind == "automatic_debit":
                reason = self._debit_assertion(clause)
                if reason != "supported":
                    return reason
            paid = bool(_PAID.search(_UNPAID.sub(" ", clause)))
            if (
                self.payment_state == "unpaid"
                and (paid or not (_UNPAID.search(clause) or _LATE.search(clause)))
            ) or (self.payment_state == "paid" and not paid):
                return "payment_condition_missing"
            if self.asks_location and not (
                _PUBLISHED.search(clause) and re.search(r"页|公告|通知|合同", clause)
            ):
                return "deadline_source_missing"
        missing = self.terms - _words(clause)
        if self.kind == "return" and product and product in declared:
            # An exact document category can supply the noun if the text just
            # says "商品"; it cannot establish other conditions in the question.
            missing -= {product.lower()}
        if self.kind == "automatic_debit" and _UNIVERSAL_NO_DEBIT.search(clause):
            # An unconditional prohibition on automatic deductions also covers
            # deductions from a card; the reverse implication is unsafe.
            missing = {w for w in missing if not _CARD.fullmatch(w)}
        if missing:
            return "query_subject_or_condition_missing"
        return "supported"

    def _debit_assertion(self, clause):
        statements = list(_DECLARED_DEBIT.finditer(clause))
        if len(statements) != 1:
            return "automatic_debit_missing_or_ambiguous"
        predicate = statements[0]
        if predicate["account"] and _words(predicate["account"]) - self.terms:
            return "debit_account_mismatch"
        tail = re.split(r"[，,]", clause[predicate.end() :], maxsplit=1)[0]
        if not _DEBIT_OBJECT.fullmatch(tail):
            return "debit_object_or_predicate_mismatch"
        money_objects = _billing_subject(clause) & {"balance", "deposit"}
        if money_objects - self.subject:
            return "debit_object_or_predicate_mismatch"
        # Validate the subject and modifiers of this predicate too. This covers
        # a limited customer segment, a second charge or a prerequisite even
        # when a passage does not explicitly label it as a restriction.
        remainder = _without(
            clause[: predicate.start()] + " " + clause[predicate.end() :],
            _SCHEDULE_REFERENCE,
            _MANUAL_ACTION,
            _UNPAID,
            _PAID,
            _PRESALE,
            _BALANCE,
            _DEPOSIT,
            _LATE,
            _DEADLINE,
        )
        additional = (
            _words(remainder) - _FRAMING - {"时", "则", "将", "须", "应", "若", "仅"}
        )
        if additional - self.terms:
            return "additional_billing_condition"
        return "supported"


def _billing_subject(text):
    return frozenset(
        name
        for name, pattern in (
            ("presale", _PRESALE),
            ("balance", _BALANCE),
            ("deposit", _DEPOSIT),
            ("deadline", _DEADLINE),
            ("human", _HUMAN),
            ("published", _PUBLISHED),
        )
        if pattern.search(text)
    )


def analyze_policy_question(text):
    """Recognize self-contained questions; other queries keep the normal lexical check."""
    tags = _tag_state(text)
    actions = _return_types(text)
    if tags and actions:
        residue = _without(
            text, _TAG_STATES, _PRODUCT, _RETURN, _RECEIPT, _WINDOW, _ELAPSED
        )
        return PolicyQuestion(
            kind="return",
            products=frozenset(_PRODUCT.findall(text)),
            actions=frozenset(actions),
            tags=frozenset(tags),
            terms=frozenset(_words(residue) - _FRAMING - _RETURN_GRAMMAR),
            needs_window=bool(_ELAPSED.search(text) or _WINDOW.search(text)),
        )
    subject = _billing_subject(text)
    automatic = _AUTOMATIC.search(text) and _DEBIT.search(text)
    if automatic or ("presale" in subject and subject & {"balance", "deposit"}):
        state = (
            "unpaid" if _UNPAID.search(text) else "paid" if _PAID.search(text) else ""
        )
        residue = _without(
            text,
            _UNPAID,
            _PAID,
            _PRESALE,
            _BALANCE,
            _DEPOSIT,
            _LATE,
            _DEADLINE,
            _HUMAN,
            _PUBLISHED,
            _LOCATE,
            _NEXT,
        )
        if "deadline" in subject and "错过" in residue:
            state = state or "unpaid"
            residue = residue.replace("错过", " ")
        if automatic:
            residue = _without(residue, _AUTOMATIC, _DEBIT)
        terms = frozenset(_words(residue) - _FRAMING)
        if subject or terms:
            return PolicyQuestion(
                kind="automatic_debit" if automatic else "billing_detail",
                products=frozenset(),
                actions=frozenset(),
                tags=frozenset(),
                terms=terms,
                needs_window=False,
                payment_state=state,
                subject=subject,
                asks_location=bool(_LOCATE.search(text)),
            )
    return None
