"""Identify policy questions and elliptical follow-ups without trusting model intent."""

import re

_POLICY = re.compile(
    r"政策|条款|规则|权益|无理由|保修|保价|质保|三包|运费险|包邮|免邮|有效期|退换条件|"
    r"手续费|违约金|退货运费|退货邮费|运费承担|积分(?:会|是否|能否|多久|何时|什么时候)?(?:失效|过期|清零)|"
    r"polic(?:y|ies)|warranty|return window|free shipping",
    re.I,
)
_SUBJECT = r"(?:退换货?|退货|换货|退款|退钱|退回|理赔|赔付|运费|邮费|积分|补贴|发票|折扣|优惠券|配送|送达)"
_CONDITION = r"(?:能否|可否|能不能|可以|可不可以|允许|支持|是否|如何|怎么|几天|多久|期限|窗口|多长|条件|谁承担|谁付|多少|收费|免费|[一二两三四五六七八九十百\d]+[天日年])"
_POLICY_QUESTION = re.compile(
    rf"{_CONDITION}.{{0,16}}{_SUBJECT}|{_SUBJECT}.{{0,16}}{_CONDITION}|"
    r"(?:能否|可否|还能|可不可以|能不能|能|可以)(?:申请|办理)?(?:退|换)(?:吗|么|不|货|款|[？?。！!]|$)|"
    r"(?:已拆|拆封|签收|吊牌).{0,16}(?:还能|能否|可以|能退)|"
    r"(?:退款金额|运费)(?:怎么计算|怎么算|如何计算)|"
    r"(?:运费|邮费|快递费|寄回费用).{0,8}(?:谁|哪方|由我|我出|自费|承担|报销)|"
    r"(?:会|是否|能否|会不会|不会|不再|不)(?:由系统)?(?:自动|自行|自己)(?:代)?(?:扣[款钱费]|划扣|划走)|"
    r"(?:自动|自行|自己)(?:代)?(?:扣[款钱费]|划走).{0,4}(?:吗|么)|"
    r"can (?:i|we) (?:get a refund|return|exchange)",
    re.I,
)
# Remove a transactional phrase, not the whole message: a customer can ask for
# both an order status and a policy explanation in adjoining clauses.
_STATUS = re.compile(
    r"(?:退款|退货运费|退货邮费|手续费|运费|邮费|退货|换货|理赔|配送|发票)(?:退款|申请|处理)?(?:进度|状态|编号|单号|记录|到哪了|到账了吗|到了吗|金额(?!怎么算|怎么计算|如何计算))|"
    r"(?:我[的这]|您[的这]|这[笔个件]|我的订单|包裹|快递|物流|订单号?.{0,16})[^，,。？！?\n]{0,14}(?:多久|什么时候|何时|明天|今天|预计)[^，,。？！?\n]{0,6}(?:送达|到货|到达)|"
    r"refund status",
    re.I,
)
_SOCIAL = re.compile(
    r"(?:你好呀?|您好|谢谢你?|感谢|再见|hi|hello|thanks)[！!。.~～\s]*", re.I
)
_NEW_TASK = re.compile(
    r"订单.{0,30}(?:状态|进度|到哪)|(?:查询?|列出|看看).{0,16}(?:物流|订单|商品)|"
    r"物流.{0,8}(?:到哪|进度)|(?:申请|办理|发起|提交).{0,5}(?:退货|换货|退款)|"
    r"投诉|取消订单|(?:换|改|更新).{0,4}(?:地址|收件人)|^(?:请)?(?:推荐|搜索)|"
    r"order status|track my order",
    re.I,
)
_FOLLOWUP = re.compile(
    r"^(?:那|如果|要是|比如|再核实|补充|还是|也行|也可以|what if|how about)|"
    r"(?:这个|这款|这种|那种|刚才|上面|之前|门店|线上|线下|商城|地域|渠道|签收|拆封|吊牌|还可以|也适用)",
    re.I,
)


_DEFERRED_TOPIC = re.compile(
    r"^(?:随后|稍后|等会儿?|之后|下次)(?:我)?(?:再|会|想)?(?:询问|问|咨询)"
)
_SERVICE_OFFER = re.compile(
    r"^(?:您)?(?:需要|要)?(?:让)?(?:我|客服)?(?:可以|可|能)?(?:帮您|帮你|为您)?(?:查询|介绍|解答|核实|说明|咨询)"
    r"(?:(?:订单|物流|商品|退换货|退货|换货|退款|配送|运费|会员|积分|售后|政策|规则|权益|问题|相关|的|和|或|、))+(?:吗|么)?"
)


def requires_policy_evidence(message, answer, previous, *, business_tool_used=False):
    for is_question, text in ((True, message), (False, answer)):
        for clause in re.split(r"[，,。；;！？!?\n]", text):
            clause = clause.strip()
            if is_question and _DEFERRED_TOPIC.match(clause):
                continue
            without_status = _STATUS.sub("", clause)
            if not is_question and _SERVICE_OFFER.fullmatch(without_status):
                # A service offer can name a policy without asserting its terms.
                continue
            if _POLICY.search(without_status) or _POLICY_QUESTION.search(
                without_status
            ):
                return True
    if (
        not previous
        or business_tool_used
        or _SOCIAL.fullmatch(message.strip())
        or _STATUS.search(message)
        or _NEW_TASK.search(message)
    ):
        return False
    if _FOLLOWUP.search(message) or message.rstrip("？?。 ").endswith("呢"):
        return True
    # A bare city, channel or product can complete the preceding request for scope.
    return previous == "needs_clarification" and bool(
        re.fullmatch(r"[\u3400-\u9fff]{2,5}[。.]?", message.strip())
    )


def scoped_policy_quotes(message, evidence):
    """Return None for ordinary lookups, or the quotes that support this scoped turn."""
    if evidence["outcome"] != "answerable" or not evidence.get(
        "embedding_model", ""
    ).startswith("local-hash"):
        return None
    from app.platform.policy_evidence import analyze_policy_question

    question = analyze_policy_question(message)
    if question is None:
        return None
    # A shortened model query or a journal replay may carry a genuine citation
    # that no longer answers the full customer question. Reject mixed evidence.
    hits = {
        hit["chunk_id"]: hit
        for hit in evidence.get("results", [])
        if hit.get("chunk_id")
    }
    quotes = []
    for cite in evidence.get("citations", []):
        hit = hits.get(cite.get("chunk_id"))
        quote = cite.get("quote", "")
        if (
            not hit
            or not question.check(
                quote, context=evidence.get("context"), metadata=hit.get("metadata")
            )["supported"]
        ):
            return []
        if quote not in quotes:
            quotes.append(quote)
    return quotes


# These are complete elliptical forms. An extra condition must not disappear
# merely because a few words in a customer message resemble a known edit.
_ACTION_ONLY = re.compile(
    r"(?:那(?:么)?|如果|要是|改成|换成)?(?:申请|办理)?(退换货?|退货|换货)"
    r"(?:也|还)?(?:行|可以|能办|一样|适用)?(?:吗|呢|么)?"
)
_TAG_ONLY = re.compile(
    r"(?:那|如果|要是)?(?:我)?(?:后来|已经|刚刚|刚)?(吊牌|商品标签)"
    r"(?:我)?(?:后来|已经|刚刚|刚|被我|还|仍)?"
    r"(没(?:有)?剪|未拆|完整|还在|剪掉|剪了|剪断|拆掉|摘掉|丢失)(?:了)?(?:呢|吗)?"
)
_PRODUCT_ONLY = re.compile(
    r"(?:那(?:么)?|如果(?:是|换成)|要是(?:是|换成)?|换成|换作|改成)"
    r"([\u3400-\u9fffA-Za-z0-9]{1,18}?)(?:呢|也一样吗|也适用吗)"
)
_UNSPECIFIED = re.compile(
    r"(?:那|如果|要是)?(?:换成)?(?:另(?:一|外一)(?:个|种|件|款)(?:商品|产品|东西)?|"
    r"其他(?:商品|产品|东西)|它|它们|那件|这个|那个)(?:也|还)?(?:能办|可以|能退|能换|适用)?(?:吗|呢)?"
)
_PAYMENT_DELTA = re.compile(
    r"(?:我|刚刚|刚|查清|查过|看过|发现|确认|其实|确实|如果|假如|要是|那|现在|"
    r"状态|显示|变成|变为|改成|刷新|刚才|预售|尾款|已经|仍然|还|未支付|逾期|过期|超过日期|后|系统|平台|"
    r"再扣一次|重复扣款|自动扣款|自动扣钱|会不会|会|吗|呢|了|[，,。\s])+"
)
_PRODUCT_PROMPT = "请说明您指的是哪件商品，以及想办理什么业务，我再为您核实。"
_CHANGE_PROMPT = "请补充商品或款项的具体情况，以及需要核实的规则。"
_LOCATION_OR_ORDER = re.compile(r"门店|线上|线下|商城|地区|渠道|订单")


def resolve_policy_followup(message, previous, had_policy_turn=False):
    """Return (independent search question, clarification, product changed).

    Only a customer's own immediately active policy question may supply
    omitted facts. Ambiguous changes never borrow subjects from model text.
    """
    from app.platform.payment_conditions import (
        parse_payment_state,
        replace_payment_state,
    )
    from app.platform.policy_evidence import (
        analyze_policy_question,
        replace_return_condition,
    )

    short = message.strip().rstrip("？?。！! ")
    if _UNSPECIFIED.fullmatch(short):
        return "", _PRODUCT_PROMPT, False
    if not previous:
        if (
            had_policy_turn
            and not _LOCATION_OR_ORDER.search(short)
            and any(
                pattern.fullmatch(short)
                for pattern in (_PRODUCT_ONLY, _ACTION_ONLY, _TAG_ONLY)
            )
        ):
            return "", _CHANGE_PROMPT, False
        return "", "", False
    prior = analyze_policy_question(previous)
    if not prior:
        return "", "", False
    if prior.kind == "return":
        action = _ACTION_ONLY.fullmatch(short)
        if action:
            return replace_return_condition(previous, action=action[1]), "", False
        tag = _TAG_ONLY.fullmatch(short)
        if tag:
            changed = tag[1] + tag[2]
            return replace_return_condition(previous, tag=changed), "", False
        product = _PRODUCT_ONLY.fullmatch(short)
        if product and not _LOCATION_OR_ORDER.search(product[1]):
            old = prior.products or prior.terms
            # A time, place, or other requirement attached to a named product
            # cannot be assumed to apply to a different purchase.
            if (
                len(old) != 1
                or (prior.products and prior.terms)
                or next(iter(old)) not in previous
            ):
                return "", _CHANGE_PROMPT, True
            return previous.replace(next(iter(old)), product[1]), "", True
    elif prior.kind in {"automatic_debit", "billing_detail", "payment_status"}:
        if parse_payment_state(short):
            normalized = replace_payment_state(short, "未支付")
            if normalized and _PAYMENT_DELTA.fullmatch(normalized):
                if "尾款" in short and "尾款" not in previous:
                    return "", _CHANGE_PROMPT, False
                changed = replace_payment_state(previous, short)
                if changed:
                    # Repeating a settled charge is a separate customer question.
                    changed = changed.replace("重复自动扣", "自动扣")
                    if re.search(r"再扣一次|重复扣", short):
                        changed = re.sub(r"(?=自动扣|自行扣)", "重复", changed, count=1)
                    return changed, "", False
    if (
        not analyze_policy_question(message)
        and not _LOCATION_OR_ORDER.search(short)
        and requires_policy_evidence(short, "", "answerable")
    ):
        # An independently phrased policy question starts a new search. If it
        # only names a new circumstance, the omitted facts cannot be guessed.
        if _POLICY.search(short) or _POLICY_QUESTION.search(short):
            return message, "", False
        return "", _CHANGE_PROMPT, False
    return "", "", False
