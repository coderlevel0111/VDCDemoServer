'use strict';
const $ = id => document.getElementById(id);
let request = null, controller = null, expiryTimer = null, ready = false;

function showStatus(message, kind = '') {
  $('status').textContent = message;
  $('status').className = `status ${kind}`;
}

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.headers.get('Content-Type')?.includes('application/json')) {
    throw new Error('服务未返回 JSON。Codespaces 请确认 8000 端口为 Public，且服务正在运行');
  }
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || '服务请求失败');
  return value;
}

function resetRequest() {
  clearTimeout(expiryTimer);
  request = null;
  $('present').hidden = true;
  $('prepare').classList.remove('secondary');
  $('prepare').disabled = !ready;
}

async function initialize() {
  $('service-url').value = location.origin;
  try {
    const config = await api('/api/mdoc/config');
    const secure = window.isSecureContext;
    const available = typeof DigitalCredential !== 'undefined' && !!navigator.credentials?.get;
    const protocol = available && typeof DigitalCredential.userAgentAllowsProtocol === 'function'
      ? await DigitalCredential.userAgentAllowsProtocol('org-iso-mdoc') : null;
    const sameOrigin = config.origin === location.origin;
    ready = secure && available && protocol !== false && sameOrigin;
    $('prepare').disabled = !ready;
    $('environment').textContent = !sameOrigin ? '地址不一致，请用诊断信息中的服务端公开地址打开网页。'
      : !secure ? '需要 HTTPS。Codespaces 请打开 8000 端口的公网地址。'
      : !available || protocol === false ? '当前浏览器不支持所需入口，请改用兼容的 iOS 26+ Safari。'
      : '浏览器入口可用。实际文档选择与授权由 iOS 和凭证提供方处理。';
    $('diagnostics').textContent = JSON.stringify({
      '当前地址': location.origin, '服务端公开地址': config.origin,
      '安全上下文': secure, '浏览器 API': available, 'org-iso-mdoc': protocol,
      '文档类型': config.doc_type,
      '发行根指纹': config.issuer_fingerprint, 'Reader 根指纹': config.reader_fingerprint,
    }, null, 2);
  } catch (error) {
    $('environment').textContent = '服务连接失败，请确认 Codespace 正在运行，且 8000 端口为 Public。';
    $('diagnostics').textContent = error.message;
  }
}

$('prepare').onclick = async () => {
  resetRequest();
  $('prepare').disabled = true;
  $('result').hidden = true;
  showStatus('正在准备一次性请求…');
  try {
    request = await api('/api/mdoc/request', {origin: location.origin});
    $('prepare').textContent = '重新准备';
    $('prepare').classList.add('secondary');
    $('present').hidden = false;
    $('present').disabled = false;
    showStatus('请求已就绪。点击“使用 iPhone 凭证”，进入系统选择和授权。');
    expiryTimer = setTimeout(() => {
      if (controller) controller.abort();
      resetRequest();
      showStatus('请求已过期，请重新准备验证。', 'error');
    }, request.expires_in * 1000);
  } catch (error) { showStatus(`准备失败：${error.message}`, 'error'); }
  finally { $('prepare').disabled = !ready; }
};

$('present').onclick = async () => {
  if (!request || controller) return;
  const current = request;
  controller = new AbortController();
  $('prepare').disabled = true;
  $('present').disabled = true;
  $('cancel').hidden = false;
  showStatus('等待 iOS 选择凭证。请在系统界面审阅并授权，或取消。');
  try {
    // This call runs directly inside the second user click, before any network await.
    const credential = await navigator.credentials.get({
      mediation: 'required', signal: controller.signal,
      digital: {requests: [{protocol: current.protocol, data: current.data}]},
    });
    if (credential?.protocol !== 'org-iso-mdoc' || typeof credential.data?.response !== 'string') {
      throw new Error('系统没有返回有效的 org-iso-mdoc 响应');
    }
    clearTimeout(expiryTimer);
    $('cancel').hidden = true;
    showStatus('已收到加密响应，正在验证发行签名、设备证明与会话…');
    const result = await api('/api/mdoc/verify', {id: current.id, response: credential.data.response});
    if (result.ok !== true) throw new Error('服务未确认验证成功');
    $('disclosed').replaceChildren();
    const labels = {school: '学校', role: '身份', credential_id: '凭证编号'};
    for (const [key, value] of Object.entries(result.disclosed)) {
      const row = document.createElement('div'), label = document.createElement('dt'), text = document.createElement('dd');
      label.textContent = labels[key] || key;
      text.textContent = key === 'role' && value === 'student' ? '学生' : String(value);
      row.append(label, text); $('disclosed').append(row);
    }
    $('checks').replaceChildren(...result.checks.map(check => {
      const item = document.createElement('li'); item.textContent = check; return item;
    }));
    $('result').hidden = false;
    showStatus('已完成本次验证。', 'success');
  } catch (error) {
    const message = error.name === 'AbortError' ? '本次请求已取消或过期，请重新准备。'
      : error.name === 'NotAllowedError' ? '系统未授权出示。请检查 App 是否注册成功、网站来源及签名权限，再重新准备。'
      : error.name === 'NotSupportedError' ? '当前系统不支持这个凭证协议，请使用兼容的 iOS Safari。'
      : `验证未完成：${error.message}。请重新准备请求。`;
    showStatus(message, 'error');
  } finally {
    controller = null;
    $('cancel').hidden = true;
    resetRequest();
  }
};

$('cancel').onclick = () => controller?.abort();
$('copy').onclick = async () => {
  try {
    await navigator.clipboard.writeText(location.origin);
    $('copy-status').textContent = '地址已复制，可粘贴到 iOS App。';
  } catch {
    $('service-url').select();
    $('copy-status').textContent = '请手动复制上方已选中的地址。';
  }
};
initialize();
