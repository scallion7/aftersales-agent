import {
  RequestClient
} from './request_client.js';
import {
  RunStream
} from './run_stream.js';
const $ = id => document.getElementById(id);
$('token').value = sessionStorage.getItem('agentToken') || '';
$('session').value = sessionStorage.getItem('agentSession') || 'demo';
let viewVersion = 0;
const labels = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  retry_wait: '等待重试',
  cancelled: '已取消',
  dead_letter: '执行失败',
  needs_reconciliation: '结果待人工核对',
  resolved: '已核对结案',
  approved: '已批准',
  pending_review: '等待人工审批',
  pending: '待处理',
  processing: '处理中',
  succeeded: '成功',
  failed: '失败',
  shipped: '已发货',
  delivered: '已签收',
  paid: '已付款'
};
let runId = '';
const client = new RequestClient(() => $('token').value);
const stream = new RunStream();
function currentView() {
  const version = viewVersion, token = $('token').value, session = $('session').value;
  return {
    token, session,
    active: () => viewVersion === version && token === $('token').value && session === $('session').value,
    request: (path, method = 'GET', body) => client.request(path, method, body, {}, token),
    sessionPath: '/v1/sessions/' + encodeURIComponent(session)
  };
}

function status(text, error = false) {
  $('status').textContent = text;
  $('status').classList.toggle('error', error)
}


function show(value, target) {
  const order = value.order,
    operation = value.operation;
  if (order) {
    $(target).textContent = '订单 ' + order.order_id + '\n状态：' + (labels[order.status] || order.status) + '\n金额：¥ ' + order.total + '\n' + (order.items || []).map(item => item.name + ' × ' + item.quantity).join('\n')
  } else if (operation) {
    $(target).textContent = '退款状态：' + (labels[operation.status] || operation.status) + '\n' + (value.message || '') + '\n处理编号：' + operation.operation_id
  } else $(target).textContent = value.message || value.error || '尚无处理结果';
}

function bubble(text) {
  if (!text) return;
  const node = document.createElement('div');
  node.className = 'bubble';
  node.textContent = text;
  $('conversation').append(node)
}

function handle(fn) {
  return async () => {
    const view = currentView();
    try {
      await fn(view)
    } catch (error) {
      if (view.active()) status(error.message, true)
    }
  }
}
async function refresh(view) {
  const [own, messages, drafts, data] = await Promise.all([
    view.request(view.sessionPath + '/ownership'), view.request(view.sessionPath + '/human-messages'),
    view.request(view.sessionPath + '/after-sale-intakes'), view.request(view.sessionPath + '/actions?include_confirmed=true')
  ]);
  if (!view.active()) return;
  $('ownership').textContent = own.state === 'human_owned' ? '人工服务中' : 'Agent 服务中';
  $('human').replaceChildren();
  for (const message of messages.messages) {
    const p = document.createElement('p');
    p.textContent = message.content;
    $('human').append(p)
  }
  $('intakes').replaceChildren();
  for (const intake of drafts.intakes) {
    const card = document.createElement('p');
    card.textContent = `订单：${intake.fields.order_id || '待补充'}；原因：${intake.fields.reason || '待补充'}；${intake.status === 'withdrawn' ? '已撤回' : '已保存，执行仍需单独确认'}`;
    if (intake.status !== 'withdrawn' && intake.fields.case_type === 'exchange') {
      card.textContent += '。换货进度请查询关联工单。';
    }
    $('intakes').append(card);
  }
  $('actions').replaceChildren();
  for (const action of data.actions) {
    const card = document.createElement('div');
    card.className = 'card';
    const title = document.createElement('h3');
    title.textContent = ({
      create_after_sale_case: '创建售后工单',
      execute_after_sale_case: '执行售后处理',
      apply_refund: '申请退款',
      inventory_command: '库存操作'
    })[action.tool_name] || action.tool_name;
    const details = document.createElement('pre');
    details.textContent = Object.entries(action.arguments).filter(([key]) => !['user_confirmed', 'evidence_provided', 'contract_version'].includes(key)).map(([key, value]) => (({
      order_id: '订单号',
      reason: '售后原因',
      case_type: '售后类型',
      case_id: '工单号',
      evidence_ids: '证据编号',
      quantity: '数量',
      sku: '商品编号'
    })[key] || key) + '：' + (typeof value === 'object' ? JSON.stringify(value) : value)).join('\n');
    const confirmed = action.status === 'confirmed';
    if (confirmed) title.textContent += '（已确认，待执行）';
    card.append(title, details);
    for (const [text, verb] of [
        confirmed ? ['继续执行', 'execute'] : ['确认并执行', 'confirm'],
        ['拒绝', 'reject']
      ]) {
      const button = document.createElement('button');
      button.textContent = text;
      button.onclick = handle(async () => {
        if (!view.active()) return;
        button.disabled = true;
        try {
          const body = {session_id: view.session};
          const path = `/v1/actions/${action.action_id}`;
          if (verb === 'reject') {
            await view.request(path + '/reject', 'POST', body);
          } else {
            if (verb === 'confirm') {
              await view.request(path + '/confirm', 'POST', {...body, arguments_hash: action.arguments_hash});
              if (!view.active()) return;
            }
            const result = await view.request(path + '/execute', 'POST', body);
            if (!view.active()) return;
            if (result.success === false) {
              status(result.error || result.message || '操作未完成，请查看状态', true);
            } else if (result.accepted) {
              bubble('请求已受理，请查询最终状态。');
            } else if (result.case) {
              bubble('工单 ' + result.case.case_id + '：' + (labels[result.case.status] || result.case.status) + (result.next_action ? '。' + result.next_action : ''));
            } else {
              bubble(result.message || (result.success ? '操作已完成' : '操作未完成，请查看状态'));
            }
            if (result.case) $('case').value = result.case.case_id
          }
          if (view.active()) await refresh(view)
        } finally {
          button.disabled = false
        }
      });
      card.append(button)
    }
    $('actions').append(card)
  }
}
async function restoreConversation(view) {
  let messages = [];
  try {
    ({messages} = await view.request(view.sessionPath + '?conversation_only=true'));
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  if (!view.active()) return;
  $('conversation').replaceChildren();
  for (const message of messages) bubble((message.role === 'user' ? '你：' : '') + message.content);
}

async function watch(view, slot, restoring = false) {
  const watchedRun = runId;
  if (!watchedRun || !view.active()) return;
  const current = () => view.active() && runId === watchedRun;
  const cursorKey = slot + ':cursor:' + watchedRun;
  if (restoring) {
    $('events').textContent = '';
    sessionStorage.removeItem(cursorKey);
  }
  const complete = await stream.watch(watchedRun, view.token, cursorKey, event => {
    if (!current()) return;
    $('events').textContent += event.event_type + '\n';
    status('执行进度：' + event.event_type);
  });
  if (!complete || !current()) return;
  const result = await view.request('/v1/runs/' + encodeURIComponent(watchedRun));
  if (!current()) return;
  status('任务状态：' + (labels[result.status] || result.status) + (result.error_code ? '（' + result.error_code + '）' : ''));
  if (restoring) {
    await restoreConversation(view);
  } else if (result.result) {
    const {reply, follow_up_question: question} = result.result;
    bubble(question && !reply.includes(question) ? reply + '\n' + question : reply);
  }
  if (current()) await refresh(view);
}

async function connect(view) {
  sessionStorage.setItem('agentToken', view.token);
  sessionStorage.setItem('agentSession', view.session);
  stream.stop();
  const slot = await client.scopeKey('run:' + view.session, view.token);
  if (!view.active()) return;
  runId = sessionStorage.getItem(slot) || '';
  await Promise.all([refresh(view), restoreConversation(view)]);
  if (!view.active()) return;
  status('会话已连接');
  if (runId) await watch(view, slot, true);
}
$('connect').onclick = handle(connect);
$('reconnect').onclick = handle(connect);
$('send').onclick = handle(async view => {
  if ($('send').disabled) return;
  const text = $('message').value;
  $('send').disabled = true;
  try {
    const slot = await client.scopeKey('run:' + view.session, view.token);
    if (!view.active()) return;
    const result = await client.write('/v1/runs', {
      message: text,
      session_id: view.session
    }, view.session, view.token);
    sessionStorage.setItem(slot, result.run_id);
    if (!view.active()) return;
    bubble('你：' + text);
    $('message').value = '';
    runId = result.run_id;
    $('events').textContent = '';
    await watch(view, slot);
  } finally {
    if (view.active()) $('send').disabled = false;
  }
});
$('cancel').onclick = handle(async view => {
  if (!runId) return;
  const watchedRun = runId;
  const result = await view.request('/v1/runs/' + encodeURIComponent(watchedRun) + '/cancel', 'POST');
  if (view.active() && runId === watchedRun) status('取消状态：' + result.cancel_state);
});
$('queryOrder').onclick = handle(async view => {
  const detail = await view.request('/v1/orders/' + encodeURIComponent($('order').value));
  if (view.active()) show(detail, 'orderResult');
});
$('queryCase').onclick = handle(async view => {
  const path = '/v1/after-sales/' + encodeURIComponent($('case').value);
  const detail = await view.request(path);
  if (!view.active()) return;
  if (detail.exchange_state) {
    $('caseResult').textContent = detail.message;
  } else {
    const operation = await view.request(path + '/operation');
    if (view.active()) show(operation, 'caseResult');
  }
});
$('search').onclick = handle(async view => {
  const result = await view.request('/v1/knowledge/search', 'POST', {
    query: $('query').value
  });
  if (!view.active()) return;
  $('citations').replaceChildren();
  const state = document.createElement('p');
  state.textContent = {
    answerable: '找到可引用证据',
    no_evidence: '没有适用证据',
    needs_clarification: '请补充地域、渠道或商品条件',
    policy_conflict: '政策存在冲突，请人工核对'
  } [result.outcome];
  $('citations').append(state);
  for (const hit of result.results) {
    const card = document.createElement('div');
    card.className = 'card';
    card.textContent = hit.doc + ' · ' + hit.section + '\n' + hit.text;
    const id = document.createElement('small');
    id.textContent = '版本 ' + hit.version_id + ' / 引用 ' + hit.chunk_id;
    const details = document.createElement('details'),
      summary = document.createElement('summary');
    summary.textContent = '查看引用定位与版本';
    details.append(summary, id);
    card.append(details);
    $('citations').append(card)
  }
});

for (const name of ['token', 'session']) $(name).addEventListener('input', () => {
  viewVersion++;
  stream.stop();
  runId = '';
  $('send').disabled = false;
  for (const id of ['conversation', 'events', 'actions', 'intakes', 'human', 'orderResult', 'caseResult', 'citations']) {
    $(id).replaceChildren();
  }
  for (const id of ['message', 'order', 'case', 'query']) $(id).value = '';
  $('ownership').textContent = '尚未连接';
  status('请连接当前会话。');
});
