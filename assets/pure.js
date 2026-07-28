/* 工作台的纯函数:不碰 DOM、不发请求,浏览器与 node 都能跑。
 *
 * 抽出来是为了能被测试钉住——尤其 esc():它守着「agent 写的数据渲染进页面」
 * 这条信任边界,曾经因为不逃逸引号而可被属性注入。
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;          // node
  } else {
    root.Pure = api;               // browser: window.Pure
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /** 分 → 展示字符串。0 或缺失一律显示「无日志」,不显示 $0(会被误读成没花钱)。 */
  function money(cents) {
    if (!cents) return '无日志';
    return '$' + Math.round(cents / 100).toLocaleString('en-US');
  }

  /** HTML 转义。文本位与属性位共用,所以引号必须一起逃——& 必须最先替换。 */
  function esc(text) {
    if (text == null) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  var LIGHTS = ['green', 'yellow', 'red'];

  /**
   * 校验 status/<项目>.json。返回 null 表示合法,否则返回人话错误。
   * 坏文件要明确报错,不能静默渲染出错误的进度——那比不显示更糟。
   */
  function validateStatus(doc) {
    if (!doc || typeof doc !== 'object') return '不是对象';
    if (typeof doc.assessed_at !== 'string' || !doc.assessed_at) return 'assessed_at 缺失';
    if (!Array.isArray(doc.modules) || !doc.modules.length) return 'modules 缺失或为空';
    for (var i = 0; i < doc.modules.length; i++) {
      var m = doc.modules[i];
      var at = 'modules[' + i + ']';
      if (!m || typeof m !== 'object') return at + ' 不是对象';
      if (typeof m.name !== 'string' || !m.name) return at + '.name 非法';
      if (typeof m.pct !== 'number' || !isFinite(m.pct) || m.pct < 0 || m.pct > 100) {
        return at + '.pct 须为 0–100 数字';
      }
      if (LIGHTS.indexOf(m.light) < 0) return at + '.light 须为 green/yellow/red';
      if (typeof m.verdict !== 'string') return at + '.verdict 非法';
    }
    return null;
  }

  /**
   * 把时间序列转成 SVG polyline 的 points 字符串。
   * 少于 2 点返回 null——一个点画不出趋势,调用方据此显示「数据不足」而不是假线。
   */
  function sparkPoints(values, width, height) {
    if (!Array.isArray(values) || values.length < 2) return null;
    var max = Math.max.apply(null, values);
    var min = Math.min.apply(null, values);
    var span = max - min || 1;              // 全平时避免除零,画成一条中线
    var stepX = width / (values.length - 1);
    return values.map(function (v, i) {
      var x = i * stepX;
      var y = height - ((v - min) / span) * height;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
  }

  return {
    money: money,
    esc: esc,
    validateStatus: validateStatus,
    sparkPoints: sparkPoints
  };
});
