"""Identify policy questions and elliptical follow-ups without trusting model intent."""

import re

_POLICY = re.compile(
    r"政策|条款|规则|权益|无理由|保修|保价|质保|三包|运费险|包邮|免邮|有效期|退换条件|"
    r"手续费|违约金|退货运费|退货邮费|运费承担|积分(?:会|是否|能否|多久|何时|什么时候)?(?:失效|过期|清零)|"
    r"polic(?:y|ies)|warranty|return window|free shipping",
    re.I,
)
_SUBJECT = r"(?:退换货?|退货|换货|退款|退钱|退回|理赔|赔付|运费|邮费|积分|补贴|发票|折扣|优惠券|配送|送达)"
_CONDITION = r"(?:能否|可否|能不能|可以|可不可以|允许|支持|是否|如何|怎么|几天|多久|期限|条件|谁承担|谁付|多少|收费|免费|[一二两三四五六七八九十百\d]+[天日年])"
_POLICY_QUESTION = re.compile(
    rf"{_CONDITION}.{{0,16}}{_SUBJECT}|{_SUBJECT}.{{0,16}}{_CONDITION}|"
    r"(?:能否|可否|还能|可不可以|能不能|能|可以)(?:申请|办理)?(?:退|换)(?:吗|么|不|货|款|[？?。！!]|$)|"
    r"(?:已拆|拆封|签收|吊牌).{0,16}(?:还能|能否|可以|能退)|"
    r"(?:退款金额|运费)(?:怎么计算|怎么算|如何计算)|"
    r"(?:运费|邮费|快递费|寄回费用).{0,8}(?:谁|哪方|由我|我出|自费|承担|报销)|"
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
