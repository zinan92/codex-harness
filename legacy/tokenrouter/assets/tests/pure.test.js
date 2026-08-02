/* node assets/tests/pure.test.js —— 零依赖,失败即非零退出。 */
'use strict';
const assert = require('assert');
const Pure = require('../pure.js');

let passed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
  } catch (err) {
    failures.push(name + '\n    ' + err.message);
  }
}

// ---------------------------------------------------------------- money
test('money: 0 与缺失显示「无日志」而非 $0', () => {
  assert.strictEqual(Pure.money(0), '无日志');
  assert.strictEqual(Pure.money(null), '无日志');
  assert.strictEqual(Pure.money(undefined), '无日志');
});

test('money: 分转美元并加千分位', () => {
  assert.strictEqual(Pure.money(100), '$1');
  assert.strictEqual(Pure.money(494093), '$4,941');
});

// ------------------------------------------------------------------ esc
test('esc: 逃逸双引号——回归钉住属性位注入漏洞', () => {
  const attack = '" onmouseover="alert(1)';
  const out = Pure.esc(attack);
  assert.ok(!out.includes('"'), '双引号必须被逃逸,否则可逃出 title="…" 注入事件处理器');
  assert.ok(out.includes('&quot;'));
});

test('esc: 逃逸单引号', () => {
  assert.ok(!Pure.esc("' onerror='x").includes("'"));
});

test('esc: 逃逸尖括号,脚本标签无法成形', () => {
  const out = Pure.esc('<script>window.x=1</script>');
  assert.ok(!out.includes('<script>'));
  assert.ok(out.includes('&lt;script&gt;'));
});

test('esc: & 最先替换,不产生双重转义错误', () => {
  // 若 & 不是最先替换,'&lt;' 会变成 '&amp;lt;' 之外的错误结果
  assert.strictEqual(Pure.esc('a & b'), 'a &amp; b');
  assert.strictEqual(Pure.esc('<'), '&lt;');
});

test('esc: null/undefined 返回空串不抛异常', () => {
  assert.strictEqual(Pure.esc(null), '');
  assert.strictEqual(Pure.esc(undefined), '');
});

// -------------------------------------------------------- validateStatus
const GOOD = {
  assessed_at: '2026-07-28',
  modules: [{ name: '风控', pct: 80, light: 'green', verdict: '最强' }]
};

test('validateStatus: 合法文档返回 null', () => {
  assert.strictEqual(Pure.validateStatus(GOOD), null);
});

test('validateStatus: pct 越界被拒', () => {
  const bad = JSON.parse(JSON.stringify(GOOD));
  bad.modules[0].pct = 150;
  assert.ok(/pct/.test(Pure.validateStatus(bad)));
});

test('validateStatus: pct 为字符串被拒', () => {
  const bad = JSON.parse(JSON.stringify(GOOD));
  bad.modules[0].pct = '80';
  assert.ok(/pct/.test(Pure.validateStatus(bad)));
});

test('validateStatus: light 非三色之一被拒', () => {
  const bad = JSON.parse(JSON.stringify(GOOD));
  bad.modules[0].light = 'blue';
  assert.ok(/light/.test(Pure.validateStatus(bad)));
});

test('validateStatus: modules 为空数组被拒', () => {
  assert.ok(/modules/.test(Pure.validateStatus({ assessed_at: '2026-07-28', modules: [] })));
});

test('validateStatus: assessed_at 缺失被拒', () => {
  assert.ok(/assessed_at/.test(Pure.validateStatus({ modules: GOOD.modules })));
});

test('validateStatus: null 与非对象被拒且不抛异常', () => {
  assert.ok(Pure.validateStatus(null));
  assert.ok(Pure.validateStatus('字符串'));
});

// ----------------------------------------------------------- sparkPoints
test('sparkPoints: 少于 2 点返回 null(不画假线)', () => {
  assert.strictEqual(Pure.sparkPoints([], 100, 20), null);
  assert.strictEqual(Pure.sparkPoints([5], 100, 20), null);
  assert.strictEqual(Pure.sparkPoints(null, 100, 20), null);
});

test('sparkPoints: 两点跨满宽度,低值在底、高值在顶', () => {
  const pts = Pure.sparkPoints([0, 10], 100, 20).split(' ');
  assert.strictEqual(pts.length, 2);
  const [x0, y0] = pts[0].split(',').map(Number);
  const [x1, y1] = pts[1].split(',').map(Number);
  assert.strictEqual(x0, 0);
  assert.strictEqual(x1, 100);
  assert.strictEqual(y0, 20);   // 最小值贴底
  assert.strictEqual(y1, 0);    // 最大值贴顶
});

test('sparkPoints: 全平序列不除零,画中线', () => {
  const pts = Pure.sparkPoints([7, 7, 7], 100, 20);
  assert.ok(pts && !pts.includes('NaN'));
});

// ------------------------------------------------------------------ 汇总
if (failures.length) {
  console.error(`FAILED ${failures.length} / ${passed + failures.length}`);
  failures.forEach(f => console.error('  ✗ ' + f));
  process.exit(1);
}
console.log(`OK  ${passed} 个用例全绿`);
