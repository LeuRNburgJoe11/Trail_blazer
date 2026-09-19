import { renderToStaticMarkup } from "react-dom/server";
import { useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
//#region src/components/DoorTrace.jsx
/**
* Motor current through one door cycle, against the Normal envelope.
*
* Two series on ONE axis (both are mA). The trace wears the module status
* colour -- black for Normal, red for Abnormal resistance -- and the envelope
* is a recessive dashed grey, so the chart never introduces a palette that
* competes with the app-wide colour code. Both are direct-labelled, so identity
* survives greyscale printing and colour-vision deficiency; exceedance regions
* additionally carry a hatch texture rather than relying on the wash alone.
*/
var W = 720;
var H = 200;
var PAD = {
	top: 16,
	right: 64,
	bottom: 28,
	left: 48
};
function niceTicks(max, count = 4) {
	const raw = max / count;
	const magnitude = Math.pow(10, Math.floor(Math.log10(raw || 1)));
	const step = [
		1,
		2,
		2.5,
		5,
		10
	].map((m) => m * magnitude).find((s) => s >= raw) ?? magnitude * 10;
	return Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step);
}
function DoorTrace({ trace, regions = [], status, startClock }) {
	const [hover, setHover] = useState(null);
	if (!trace || trace.length < 2) return null;
	const traceColor = status !== "Normal" ? "var(--status-fault)" : "var(--status-clear)";
	const duration = trace[trace.length - 1].t || 1;
	const yMax = Math.max(...trace.map((p) => Math.max(p.current, p.envelope))) * 1.08;
	const x = (t) => PAD.left + t / duration * (W - PAD.left - PAD.right);
	const y = (v) => H - PAD.bottom - v / yMax * (H - PAD.top - PAD.bottom);
	const path = (key) => trace.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");
	function onMove(event) {
		const box = event.currentTarget.getBoundingClientRect();
		const ratio = (event.clientX - box.left) / box.width;
		const t = Math.max(0, Math.min(duration, (ratio * W - PAD.left) / (W - PAD.left - PAD.right) * duration));
		let nearest = 0;
		for (let i = 1; i < trace.length; i += 1) if (Math.abs(trace[i].t - t) < Math.abs(trace[nearest].t - t)) nearest = i;
		setHover(trace[nearest]);
	}
	return /* @__PURE__ */ jsxs("figure", {
		className: "trace",
		children: [/* @__PURE__ */ jsxs("svg", {
			viewBox: `0 0 ${W} ${H}`,
			className: "trace__svg",
			role: "img",
			"aria-label": `Motor current through the cycle against the Normal envelope. ${regions.length} interval(s) above the envelope.`,
			onMouseMove: onMove,
			onMouseLeave: () => setHover(null),
			children: [
				/* @__PURE__ */ jsx("defs", { children: /* @__PURE__ */ jsx("pattern", {
					id: "trace-hatch",
					width: "6",
					height: "6",
					patternTransform: "rotate(45)",
					patternUnits: "userSpaceOnUse",
					children: /* @__PURE__ */ jsx("line", {
						x1: "0",
						y1: "0",
						x2: "0",
						y2: "6",
						stroke: "var(--status-fault)",
						strokeWidth: "1.5",
						opacity: "0.28"
					})
				}) }),
				niceTicks(yMax).map((value) => /* @__PURE__ */ jsxs("g", { children: [/* @__PURE__ */ jsx("line", {
					x1: PAD.left,
					x2: W - PAD.right,
					y1: y(value),
					y2: y(value),
					className: "trace__grid"
				}), /* @__PURE__ */ jsx("text", {
					x: PAD.left - 8,
					y: y(value) + 4,
					className: "trace__axis",
					textAnchor: "end",
					children: value
				})] }, value)),
				regions.map((region) => /* @__PURE__ */ jsx("rect", {
					x: x(region.start_offset),
					y: PAD.top,
					width: Math.max(x(region.end_offset) - x(region.start_offset), 1.5),
					height: H - PAD.top - PAD.bottom,
					fill: "url(#trace-hatch)"
				}, `${region.start_offset}-${region.end_offset}`)),
				/* @__PURE__ */ jsx("line", {
					x1: PAD.left,
					x2: W - PAD.right,
					y1: H - PAD.bottom,
					y2: H - PAD.bottom,
					className: "trace__axis-line"
				}),
				/* @__PURE__ */ jsx("path", {
					d: path("envelope"),
					className: "trace__envelope"
				}),
				/* @__PURE__ */ jsx("path", {
					d: path("current"),
					style: { stroke: traceColor },
					className: "trace__current"
				}),
				/* @__PURE__ */ jsx("text", {
					x: W - PAD.right + 6,
					y: y(trace[trace.length - 1].current) + 4,
					className: "trace__label",
					style: { fill: traceColor },
					children: "Current"
				}),
				/* @__PURE__ */ jsx("text", {
					x: W - PAD.right + 6,
					y: y(trace[trace.length - 1].envelope) + 4,
					className: "trace__label trace__label--muted",
					children: "Normal"
				}),
				[
					0,
					duration / 2,
					duration
				].map((t) => /* @__PURE__ */ jsxs("text", {
					x: x(t),
					y: 192,
					className: "trace__axis",
					textAnchor: "middle",
					children: [
						"+",
						t.toFixed(2),
						"s"
					]
				}, t)),
				hover && /* @__PURE__ */ jsxs("g", {
					pointerEvents: "none",
					children: [
						/* @__PURE__ */ jsx("line", {
							x1: x(hover.t),
							x2: x(hover.t),
							y1: PAD.top,
							y2: H - PAD.bottom,
							className: "trace__crosshair"
						}),
						/* @__PURE__ */ jsx("circle", {
							cx: x(hover.t),
							cy: y(hover.current),
							r: "4",
							style: { fill: traceColor }
						}),
						/* @__PURE__ */ jsx("circle", {
							cx: x(hover.t),
							cy: y(hover.envelope),
							r: "3.5",
							className: "trace__dot-envelope"
						})
					]
				})
			]
		}), /* @__PURE__ */ jsx("figcaption", {
			className: "trace__caption",
			children: hover ? /* @__PURE__ */ jsxs("span", {
				className: "trace__readout",
				children: [
					"+",
					hover.t.toFixed(2),
					"s · current ",
					/* @__PURE__ */ jsxs("strong", { children: [hover.current, " mA"] }),
					" · Normal envelope",
					" ",
					hover.envelope,
					" mA"
				]
			}) : /* @__PURE__ */ jsxs("span", { children: [
				"Motor current (mA) from ",
				startClock,
				". Hatched bands mark where this cycle draws above the Normal envelope",
				regions.length ? "" : " (none in this cycle)",
				"."
			] })
		})]
	});
}
//#endregion
//#region src/__ssrdoor.jsx
var bad = { rows: [{
	"source_file": "Test.csv",
	"start_time": "2023-7-5-0-5-46-252",
	"end_time": "2023-7-5-0-5-49-992",
	"prediction": "Abnormal resistance",
	"confidence": .995,
	"evidence": {
		"operation": "Close",
		"start_time": "2023-7-5-0-5-46-252",
		"end_time": "2023-7-5-0-5-49-992",
		"start_clock": "00:05:46.25",
		"end_clock": "00:05:49.99",
		"duration_seconds": 3.74,
		"n_samples": 188,
		"envelope_available": true,
		"fraction_above_envelope": .64,
		"regions": [
			{
				"start_offset": .305,
				"end_offset": .458,
				"seconds": .153,
				"start_clock": "00:05:46.55",
				"end_clock": "00:05:46.70"
			},
			{
				"start_offset": .916,
				"end_offset": 1.298,
				"seconds": .382,
				"start_clock": "00:05:47.16",
				"end_clock": "00:05:47.54"
			},
			{
				"start_offset": 1.45,
				"end_offset": 2.595,
				"seconds": 1.145,
				"start_clock": "00:05:47.70",
				"end_clock": "00:05:48.84"
			},
			{
				"start_offset": 2.977,
				"end_offset": 3.282,
				"seconds": .305,
				"start_clock": "00:05:49.22",
				"end_clock": "00:05:49.53"
			}
		],
		"indicators": [
			{
				"name": "energy_proxy",
				"label": "Energy proxy (current x voltage)",
				"value": 2734841.4894,
				"normal_median": 1830346.6812,
				"ratio": 1.494,
				"unit": ""
			},
			{
				"name": "current_integral",
				"label": "Current integral over the cycle",
				"value": 2099.9105,
				"normal_median": 1561.0788,
				"ratio": 1.345,
				"unit": ""
			},
			{
				"name": "current_mean",
				"label": "Mean motor current",
				"value": 561.4734,
				"normal_median": 424.0001,
				"ratio": 1.324,
				"unit": " mA"
			},
			{
				"name": "current_rms",
				"label": "RMS motor current",
				"value": 739.5766,
				"normal_median": 667.7732,
				"ratio": 1.108,
				"unit": " mA"
			},
			{
				"name": "position_stagnation",
				"label": "Fraction of the cycle with no leaf movement",
				"value": .0749,
				"normal_median": .0707,
				"ratio": 1.059,
				"unit": ""
			}
		],
		"trace": [
			{
				"t": 0,
				"current": 112,
				"envelope": 115
			},
			{
				"t": .02,
				"current": 132,
				"envelope": 206.8
			},
			{
				"t": .04,
				"current": 176,
				"envelope": 298.5
			},
			{
				"t": .06,
				"current": 312,
				"envelope": 390.3
			},
			{
				"t": .08,
				"current": 467,
				"envelope": 494.1
			},
			{
				"t": .1,
				"current": 641,
				"envelope": 651.6
			},
			{
				"t": .12,
				"current": 835,
				"envelope": 809.2
			},
			{
				"t": .14,
				"current": 979,
				"envelope": 966.7
			},
			{
				"t": .16,
				"current": 1123,
				"envelope": 1102.2
			},
			{
				"t": .18,
				"current": 1217,
				"envelope": 1200
			},
			{
				"t": .2,
				"current": 1287,
				"envelope": 1297.7
			},
			{
				"t": .22,
				"current": 1358,
				"envelope": 1395.5
			},
			{
				"t": .24,
				"current": 1387,
				"envelope": 1386.3
			},
			{
				"t": .26,
				"current": 1373,
				"envelope": 1290.1
			},
			{
				"t": .28,
				"current": 1305,
				"envelope": 1193.9
			},
			{
				"t": .3,
				"current": 1205,
				"envelope": 1097.6
			},
			{
				"t": .32,
				"current": 1046,
				"envelope": 941.7
			},
			{
				"t": .34,
				"current": 858,
				"envelope": 764.2
			},
			{
				"t": .36,
				"current": 676,
				"envelope": 586.8
			},
			{
				"t": .38,
				"current": 520,
				"envelope": 409.3
			},
			{
				"t": .4,
				"current": 397,
				"envelope": 346.5
			},
			{
				"t": .42,
				"current": 306,
				"envelope": 294
			},
			{
				"t": .44,
				"current": 250,
				"envelope": 241.4
			},
			{
				"t": .46,
				"current": 218,
				"envelope": 194.9
			},
			{
				"t": .48,
				"current": 194,
				"envelope": 201.4
			},
			{
				"t": .5,
				"current": 176,
				"envelope": 207.9
			},
			{
				"t": .52,
				"current": 182,
				"envelope": 214.4
			},
			{
				"t": .54,
				"current": 200,
				"envelope": 221.6
			},
			{
				"t": .56,
				"current": 223,
				"envelope": 230.4
			},
			{
				"t": .58,
				"current": 244,
				"envelope": 239.3
			},
			{
				"t": .6,
				"current": 259,
				"envelope": 248.1
			},
			{
				"t": .62,
				"current": 267,
				"envelope": 261.3
			},
			{
				"t": .64,
				"current": 279,
				"envelope": 279.6
			},
			{
				"t": .66,
				"current": 294,
				"envelope": 297.9
			},
			{
				"t": .68,
				"current": 297,
				"envelope": 316.2
			},
			{
				"t": .7,
				"current": 300,
				"envelope": 324.3
			},
			{
				"t": .72,
				"current": 294,
				"envelope": 327
			},
			{
				"t": .74,
				"current": 291,
				"envelope": 329.7
			},
			{
				"t": .76,
				"current": 303,
				"envelope": 332.4
			},
			{
				"t": .78,
				"current": 297,
				"envelope": 322.5
			},
			{
				"t": .8,
				"current": 279,
				"envelope": 310.1
			},
			{
				"t": .82,
				"current": 270,
				"envelope": 297.7
			},
			{
				"t": .84,
				"current": 276,
				"envelope": 285.4
			},
			{
				"t": .86,
				"current": 276,
				"envelope": 278.6
			},
			{
				"t": .88,
				"current": 273,
				"envelope": 271.7
			},
			{
				"t": .9,
				"current": 262,
				"envelope": 264.8
			},
			{
				"t": .92,
				"current": 267,
				"envelope": 259.4
			},
			{
				"t": .94,
				"current": 273,
				"envelope": 259.5
			},
			{
				"t": .96,
				"current": 273,
				"envelope": 259.6
			},
			{
				"t": .98,
				"current": 273,
				"envelope": 259.7
			},
			{
				"t": 1,
				"current": 273,
				"envelope": 260.5
			},
			{
				"t": 1.02,
				"current": 285,
				"envelope": 262.5
			},
			{
				"t": 1.04,
				"current": 303,
				"envelope": 264.4
			},
			{
				"t": 1.06,
				"current": 303,
				"envelope": 266.3
			},
			{
				"t": 1.08,
				"current": 297,
				"envelope": 267.1
			},
			{
				"t": 1.1,
				"current": 300,
				"envelope": 267.1
			},
			{
				"t": 1.12,
				"current": 309,
				"envelope": 267.1
			},
			{
				"t": 1.14,
				"current": 315,
				"envelope": 267.1
			},
			{
				"t": 1.16,
				"current": 312,
				"envelope": 268.9
			},
			{
				"t": 1.18,
				"current": 312,
				"envelope": 271.2
			},
			{
				"t": 1.2,
				"current": 315,
				"envelope": 273.6
			},
			{
				"t": 1.22,
				"current": 312,
				"envelope": 275.9
			},
			{
				"t": 1.24,
				"current": 297,
				"envelope": 274.8
			},
			{
				"t": 1.26,
				"current": 285,
				"envelope": 273.5
			},
			{
				"t": 1.28,
				"current": 288,
				"envelope": 272.2
			},
			{
				"t": 1.3,
				"current": 288,
				"envelope": 270.9
			},
			{
				"t": 1.32,
				"current": 282,
				"envelope": 269.7
			},
			{
				"t": 1.34,
				"current": 279,
				"envelope": 268.5
			},
			{
				"t": 1.36,
				"current": 265,
				"envelope": 267.3
			},
			{
				"t": 1.38,
				"current": 256,
				"envelope": 266.2
			},
			{
				"t": 1.4,
				"current": 247,
				"envelope": 265
			},
			{
				"t": 1.42,
				"current": 238,
				"envelope": 263.8
			},
			{
				"t": 1.44,
				"current": 273,
				"envelope": 262.6
			},
			{
				"t": 1.46,
				"current": 306,
				"envelope": 262.3
			},
			{
				"t": 1.48,
				"current": 367,
				"envelope": 263.1
			},
			{
				"t": 1.5,
				"current": 417,
				"envelope": 263.8
			},
			{
				"t": 1.52,
				"current": 467,
				"envelope": 264.5
			},
			{
				"t": 1.54,
				"current": 511,
				"envelope": 263.7
			},
			{
				"t": 1.56,
				"current": 573,
				"envelope": 262.2
			},
			{
				"t": 1.58,
				"current": 638,
				"envelope": 260.7
			},
			{
				"t": 1.6,
				"current": 711,
				"envelope": 259.2
			},
			{
				"t": 1.62,
				"current": 802,
				"envelope": 260.2
			},
			{
				"t": 1.64,
				"current": 873,
				"envelope": 261.6
			},
			{
				"t": 1.66,
				"current": 941,
				"envelope": 263
			},
			{
				"t": 1.68,
				"current": 1005,
				"envelope": 264.1
			},
			{
				"t": 1.7,
				"current": 1029,
				"envelope": 260.4
			},
			{
				"t": 1.72,
				"current": 1058,
				"envelope": 256.7
			},
			{
				"t": 1.74,
				"current": 1049,
				"envelope": 253
			},
			{
				"t": 1.76,
				"current": 1029,
				"envelope": 249.1
			},
			{
				"t": 1.78,
				"current": 999,
				"envelope": 244.2
			},
			{
				"t": 1.8,
				"current": 970,
				"envelope": 239.3
			},
			{
				"t": 1.82,
				"current": 949,
				"envelope": 234.4
			},
			{
				"t": 1.84,
				"current": 947,
				"envelope": 229.8
			},
			{
				"t": 1.86,
				"current": 944,
				"envelope": 225.6
			},
			{
				"t": 1.88,
				"current": 944,
				"envelope": 221.5
			},
			{
				"t": 1.9,
				"current": 932,
				"envelope": 217.3
			},
			{
				"t": 1.92,
				"current": 929,
				"envelope": 210.2
			},
			{
				"t": 1.94,
				"current": 929,
				"envelope": 201
			},
			{
				"t": 1.96,
				"current": 929,
				"envelope": 191.8
			},
			{
				"t": 1.98,
				"current": 917,
				"envelope": 182.7
			},
			{
				"t": 2,
				"current": 914,
				"envelope": 174.4
			},
			{
				"t": 2.02,
				"current": 894,
				"envelope": 166.5
			},
			{
				"t": 2.04,
				"current": 867,
				"envelope": 158.6
			},
			{
				"t": 2.06,
				"current": 829,
				"envelope": 150.6
			},
			{
				"t": 2.08,
				"current": 785,
				"envelope": 134.1
			},
			{
				"t": 2.1,
				"current": 732,
				"envelope": 117.2
			},
			{
				"t": 2.12,
				"current": 667,
				"envelope": 100.3
			},
			{
				"t": 2.14,
				"current": 594,
				"envelope": 83.7
			},
			{
				"t": 2.16,
				"current": 526,
				"envelope": 68.5
			},
			{
				"t": 2.18,
				"current": 459,
				"envelope": 53.3
			},
			{
				"t": 2.2,
				"current": 388,
				"envelope": 38.1
			},
			{
				"t": 2.22,
				"current": 303,
				"envelope": 25.5
			},
			{
				"t": 2.24,
				"current": 229,
				"envelope": 18.2
			},
			{
				"t": 2.26,
				"current": 182,
				"envelope": 10.9
			},
			{
				"t": 2.28,
				"current": 144,
				"envelope": 3.6
			},
			{
				"t": 2.3,
				"current": 126,
				"envelope": 0
			},
			{
				"t": 2.32,
				"current": 112,
				"envelope": 0
			},
			{
				"t": 2.34,
				"current": 112,
				"envelope": 0
			},
			{
				"t": 2.36,
				"current": 115,
				"envelope": 0
			},
			{
				"t": 2.38,
				"current": 115,
				"envelope": 0
			},
			{
				"t": 2.4,
				"current": 123,
				"envelope": 0
			},
			{
				"t": 2.42,
				"current": 141,
				"envelope": 0
			},
			{
				"t": 2.44,
				"current": 159,
				"envelope": 0
			},
			{
				"t": 2.46,
				"current": 185,
				"envelope": 8.4
			},
			{
				"t": 2.48,
				"current": 203,
				"envelope": 18
			},
			{
				"t": 2.5,
				"current": 206,
				"envelope": 27.6
			},
			{
				"t": 2.52,
				"current": 203,
				"envelope": 38.4
			},
			{
				"t": 2.54,
				"current": 194,
				"envelope": 69.3
			},
			{
				"t": 2.56,
				"current": 179,
				"envelope": 100.1
			},
			{
				"t": 2.58,
				"current": 176,
				"envelope": 130.9
			},
			{
				"t": 2.6,
				"current": 170,
				"envelope": 165.1
			},
			{
				"t": 2.62,
				"current": 156,
				"envelope": 209.6
			},
			{
				"t": 2.64,
				"current": 156,
				"envelope": 254.2
			},
			{
				"t": 2.66,
				"current": 159,
				"envelope": 298.7
			},
			{
				"t": 2.68,
				"current": 162,
				"envelope": 330.4
			},
			{
				"t": 2.7,
				"current": 173,
				"envelope": 344.8
			},
			{
				"t": 2.72,
				"current": 185,
				"envelope": 359.1
			},
			{
				"t": 2.74,
				"current": 194,
				"envelope": 373.5
			},
			{
				"t": 2.76,
				"current": 194,
				"envelope": 380.1
			},
			{
				"t": 2.78,
				"current": 200,
				"envelope": 381.7
			},
			{
				"t": 2.8,
				"current": 203,
				"envelope": 383.3
			},
			{
				"t": 2.82,
				"current": 206,
				"envelope": 384.9
			},
			{
				"t": 2.84,
				"current": 223,
				"envelope": 375.9
			},
			{
				"t": 2.86,
				"current": 250,
				"envelope": 364.2
			},
			{
				"t": 2.88,
				"current": 276,
				"envelope": 352.5
			},
			{
				"t": 2.9,
				"current": 291,
				"envelope": 340.8
			},
			{
				"t": 2.92,
				"current": 291,
				"envelope": 317.5
			},
			{
				"t": 2.94,
				"current": 291,
				"envelope": 293.9
			},
			{
				"t": 2.96,
				"current": 288,
				"envelope": 270.4
			},
			{
				"t": 2.98,
				"current": 285,
				"envelope": 251.8
			},
			{
				"t": 3,
				"current": 279,
				"envelope": 258.8
			},
			{
				"t": 3.02,
				"current": 279,
				"envelope": 265.8
			},
			{
				"t": 3.04,
				"current": 300,
				"envelope": 272.8
			},
			{
				"t": 3.06,
				"current": 320,
				"envelope": 278.6
			},
			{
				"t": 3.08,
				"current": 353,
				"envelope": 282.3
			},
			{
				"t": 3.1,
				"current": 388,
				"envelope": 285.9
			},
			{
				"t": 3.12,
				"current": 414,
				"envelope": 289.5
			},
			{
				"t": 3.14,
				"current": 435,
				"envelope": 294.2
			},
			{
				"t": 3.16,
				"current": 456,
				"envelope": 299.7
			},
			{
				"t": 3.18,
				"current": 459,
				"envelope": 305.2
			},
			{
				"t": 3.2,
				"current": 461,
				"envelope": 310.7
			},
			{
				"t": 3.22,
				"current": 453,
				"envelope": 314.3
			},
			{
				"t": 3.24,
				"current": 453,
				"envelope": 317.1
			},
			{
				"t": 3.26,
				"current": 441,
				"envelope": 320
			},
			{
				"t": 3.28,
				"current": 441,
				"envelope": 322.8
			},
			{
				"t": 3.3,
				"current": 441,
				"envelope": 395.5
			},
			{
				"t": 3.32,
				"current": 441,
				"envelope": 476.2
			},
			{
				"t": 3.34,
				"current": 444,
				"envelope": 556.9
			},
			{
				"t": 3.36,
				"current": 464,
				"envelope": 656.1
			},
			{
				"t": 3.38,
				"current": 506,
				"envelope": 963.3
			},
			{
				"t": 3.4,
				"current": 556,
				"envelope": 1270.6
			},
			{
				"t": 3.42,
				"current": 614,
				"envelope": 1577.8
			},
			{
				"t": 3.44,
				"current": 726,
				"envelope": 1823.2
			},
			{
				"t": 3.46,
				"current": 791,
				"envelope": 1897.3
			},
			{
				"t": 3.48,
				"current": 832,
				"envelope": 1971.4
			},
			{
				"t": 3.5,
				"current": 1329,
				"envelope": 2045.5
			},
			{
				"t": 3.52,
				"current": 1784,
				"envelope": 2074
			},
			{
				"t": 3.54,
				"current": 1931,
				"envelope": 2046.4
			},
			{
				"t": 3.56,
				"current": 1937,
				"envelope": 2018.8
			},
			{
				"t": 3.58,
				"current": 1952,
				"envelope": 1991.3
			},
			{
				"t": 3.6,
				"current": 1955,
				"envelope": 1984.6
			},
			{
				"t": 3.62,
				"current": 1969,
				"envelope": 1990.1
			},
			{
				"t": 3.64,
				"current": 1978,
				"envelope": 1995.6
			},
			{
				"t": 3.66,
				"current": 1984,
				"envelope": 2001
			},
			{
				"t": 3.68,
				"current": 1990,
				"envelope": 2002.7
			},
			{
				"t": 3.7,
				"current": 1993,
				"envelope": 2003.4
			},
			{
				"t": 3.72,
				"current": 1993,
				"envelope": 2004.2
			},
			{
				"t": 3.74,
				"current": 1999,
				"envelope": 2005
			}
		],
		"reason": "Motor current runs above the Normal envelope for 64% of the close cycle, sustained rather than a brief spike. Energy proxy (current x voltage) is 1.49x the Normal median; current integral over the cycle is 1.34x the Normal median. Longest elevated window 00:05:47.70 to 00:05:48.84 (1.15 s) -- inspect there for binding or an obstruction."
	}
}, {
	"source_file": "Test.csv",
	"start_time": "2023-7-5-0-0-0-0",
	"end_time": "2023-7-5-0-0-3-760",
	"prediction": "Normal",
	"confidence": .745,
	"evidence": {
		"operation": "Close",
		"start_time": "2023-7-5-0-0-0-0",
		"end_time": "2023-7-5-0-0-3-760",
		"start_clock": "00:00:00.00",
		"end_clock": "00:00:03.76",
		"duration_seconds": 3.76,
		"n_samples": 189,
		"envelope_available": true,
		"fraction_above_envelope": .5,
		"regions": [
			{
				"start_offset": 0,
				"end_offset": .153,
				"seconds": .153,
				"start_clock": "00:00:00.00",
				"end_clock": "00:00:00.15"
			},
			{
				"start_offset": .46,
				"end_offset": .691,
				"seconds": .23,
				"start_clock": "00:00:00.46",
				"end_clock": "00:00:00.69"
			},
			{
				"start_offset": .921,
				"end_offset": 1.458,
				"seconds": .537,
				"start_clock": "00:00:00.92",
				"end_clock": "00:00:01.45"
			},
			{
				"start_offset": 2.532,
				"end_offset": 2.686,
				"seconds": .153,
				"start_clock": "00:00:02.53",
				"end_clock": "00:00:02.68"
			},
			{
				"start_offset": 2.993,
				"end_offset": 3.223,
				"seconds": .23,
				"start_clock": "00:00:02.99",
				"end_clock": "00:00:03.22"
			}
		],
		"indicators": [
			{
				"name": "position_stagnation",
				"label": "Fraction of the cycle with no leaf movement",
				"value": .0798,
				"normal_median": .0707,
				"ratio": 1.129,
				"unit": ""
			},
			{
				"name": "current_integral",
				"label": "Current integral over the cycle",
				"value": 1744.5604,
				"normal_median": 1561.0788,
				"ratio": 1.118,
				"unit": ""
			},
			{
				"name": "current_mean",
				"label": "Mean motor current",
				"value": 463.9788,
				"normal_median": 424.0001,
				"ratio": 1.094,
				"unit": " mA"
			},
			{
				"name": "energy_proxy",
				"label": "Energy proxy (current x voltage)",
				"value": 1958017.4603,
				"normal_median": 1830346.6812,
				"ratio": 1.07,
				"unit": ""
			},
			{
				"name": "current_rms",
				"label": "RMS motor current",
				"value": 712.7249,
				"normal_median": 667.7732,
				"ratio": 1.067,
				"unit": " mA"
			}
		],
		"trace": [
			{
				"t": 0,
				"current": 121,
				"envelope": 115
			},
			{
				"t": .02,
				"current": 150,
				"envelope": 206.3
			},
			{
				"t": .04,
				"current": 232,
				"envelope": 297.5
			},
			{
				"t": .06,
				"current": 409,
				"envelope": 388.8
			},
			{
				"t": .08,
				"current": 588,
				"envelope": 490.8
			},
			{
				"t": .1,
				"current": 758,
				"envelope": 647.4
			},
			{
				"t": .12,
				"current": 923,
				"envelope": 804.1
			},
			{
				"t": .14,
				"current": 1073,
				"envelope": 960.8
			},
			{
				"t": .16,
				"current": 1240,
				"envelope": 1098.1
			},
			{
				"t": .18,
				"current": 1376,
				"envelope": 1195.3
			},
			{
				"t": .2,
				"current": 1443,
				"envelope": 1292.5
			},
			{
				"t": .22,
				"current": 1461,
				"envelope": 1389.8
			},
			{
				"t": .24,
				"current": 1402,
				"envelope": 1392.5
			},
			{
				"t": .26,
				"current": 1279,
				"envelope": 1296.8
			},
			{
				"t": .28,
				"current": 1082,
				"envelope": 1201
			},
			{
				"t": .3,
				"current": 861,
				"envelope": 1105.3
			},
			{
				"t": .32,
				"current": 655,
				"envelope": 956.8
			},
			{
				"t": .34,
				"current": 491,
				"envelope": 780.3
			},
			{
				"t": .36,
				"current": 359,
				"envelope": 603.8
			},
			{
				"t": .38,
				"current": 276,
				"envelope": 427.2
			},
			{
				"t": .4,
				"current": 232,
				"envelope": 352.1
			},
			{
				"t": .42,
				"current": 200,
				"envelope": 299.9
			},
			{
				"t": .44,
				"current": 191,
				"envelope": 247.6
			},
			{
				"t": .46,
				"current": 194,
				"envelope": 195.3
			},
			{
				"t": .48,
				"current": 209,
				"envelope": 200.6
			},
			{
				"t": .5,
				"current": 223,
				"envelope": 207
			},
			{
				"t": .52,
				"current": 235,
				"envelope": 213.5
			},
			{
				"t": .54,
				"current": 241,
				"envelope": 220.3
			},
			{
				"t": .56,
				"current": 259,
				"envelope": 229.1
			},
			{
				"t": .58,
				"current": 259,
				"envelope": 237.9
			},
			{
				"t": .6,
				"current": 253,
				"envelope": 246.7
			},
			{
				"t": .62,
				"current": 276,
				"envelope": 258.3
			},
			{
				"t": .64,
				"current": 309,
				"envelope": 276.5
			},
			{
				"t": .66,
				"current": 329,
				"envelope": 294.7
			},
			{
				"t": .68,
				"current": 338,
				"envelope": 312.9
			},
			{
				"t": .7,
				"current": 344,
				"envelope": 323.8
			},
			{
				"t": .72,
				"current": 353,
				"envelope": 326.5
			},
			{
				"t": .74,
				"current": 341,
				"envelope": 329.1
			},
			{
				"t": .76,
				"current": 323,
				"envelope": 331.8
			},
			{
				"t": .78,
				"current": 303,
				"envelope": 325
			},
			{
				"t": .8,
				"current": 282,
				"envelope": 312.7
			},
			{
				"t": .82,
				"current": 267,
				"envelope": 300.4
			},
			{
				"t": .84,
				"current": 259,
				"envelope": 288.1
			},
			{
				"t": .86,
				"current": 262,
				"envelope": 280.1
			},
			{
				"t": .88,
				"current": 262,
				"envelope": 273.3
			},
			{
				"t": .9,
				"current": 259,
				"envelope": 266.5
			},
			{
				"t": .92,
				"current": 265,
				"envelope": 259.6
			},
			{
				"t": .94,
				"current": 276,
				"envelope": 259.5
			},
			{
				"t": .96,
				"current": 267,
				"envelope": 259.6
			},
			{
				"t": .98,
				"current": 265,
				"envelope": 259.7
			},
			{
				"t": 1,
				"current": 276,
				"envelope": 260
			},
			{
				"t": 1.02,
				"current": 267,
				"envelope": 261.9
			},
			{
				"t": 1.04,
				"current": 267,
				"envelope": 263.9
			},
			{
				"t": 1.06,
				"current": 282,
				"envelope": 265.8
			},
			{
				"t": 1.08,
				"current": 285,
				"envelope": 267.1
			},
			{
				"t": 1.1,
				"current": 267,
				"envelope": 267.1
			},
			{
				"t": 1.12,
				"current": 270,
				"envelope": 267.1
			},
			{
				"t": 1.14,
				"current": 279,
				"envelope": 267.1
			},
			{
				"t": 1.16,
				"current": 267,
				"envelope": 268.2
			},
			{
				"t": 1.18,
				"current": 270,
				"envelope": 270.5
			},
			{
				"t": 1.2,
				"current": 282,
				"envelope": 272.8
			},
			{
				"t": 1.22,
				"current": 279,
				"envelope": 275.2
			},
			{
				"t": 1.24,
				"current": 276,
				"envelope": 275.3
			},
			{
				"t": 1.26,
				"current": 276,
				"envelope": 273.9
			},
			{
				"t": 1.28,
				"current": 276,
				"envelope": 272.6
			},
			{
				"t": 1.3,
				"current": 273,
				"envelope": 271.3
			},
			{
				"t": 1.32,
				"current": 273,
				"envelope": 270.1
			},
			{
				"t": 1.34,
				"current": 276,
				"envelope": 268.9
			},
			{
				"t": 1.36,
				"current": 276,
				"envelope": 267.8
			},
			{
				"t": 1.38,
				"current": 273,
				"envelope": 266.6
			},
			{
				"t": 1.4,
				"current": 270,
				"envelope": 265.4
			},
			{
				"t": 1.42,
				"current": 276,
				"envelope": 264.2
			},
			{
				"t": 1.44,
				"current": 270,
				"envelope": 263.1
			},
			{
				"t": 1.46,
				"current": 270,
				"envelope": 262.1
			},
			{
				"t": 1.48,
				"current": 273,
				"envelope": 262.8
			},
			{
				"t": 1.5,
				"current": 267,
				"envelope": 263.5
			},
			{
				"t": 1.52,
				"current": 262,
				"envelope": 264.2
			},
			{
				"t": 1.54,
				"current": 262,
				"envelope": 264.3
			},
			{
				"t": 1.56,
				"current": 262,
				"envelope": 262.8
			},
			{
				"t": 1.58,
				"current": 262,
				"envelope": 261.3
			},
			{
				"t": 1.6,
				"current": 262,
				"envelope": 259.9
			},
			{
				"t": 1.62,
				"current": 270,
				"envelope": 259.6
			},
			{
				"t": 1.64,
				"current": 270,
				"envelope": 261
			},
			{
				"t": 1.66,
				"current": 259,
				"envelope": 262.3
			},
			{
				"t": 1.68,
				"current": 265,
				"envelope": 263.7
			},
			{
				"t": 1.7,
				"current": 259,
				"envelope": 262.1
			},
			{
				"t": 1.72,
				"current": 250,
				"envelope": 258.4
			},
			{
				"t": 1.74,
				"current": 253,
				"envelope": 254.7
			},
			{
				"t": 1.76,
				"current": 253,
				"envelope": 251.1
			},
			{
				"t": 1.78,
				"current": 241,
				"envelope": 246.5
			},
			{
				"t": 1.8,
				"current": 232,
				"envelope": 241.6
			},
			{
				"t": 1.82,
				"current": 232,
				"envelope": 236.7
			},
			{
				"t": 1.84,
				"current": 232,
				"envelope": 231.9
			},
			{
				"t": 1.86,
				"current": 212,
				"envelope": 227.7
			},
			{
				"t": 1.88,
				"current": 206,
				"envelope": 223.6
			},
			{
				"t": 1.9,
				"current": 206,
				"envelope": 219.4
			},
			{
				"t": 1.92,
				"current": 197,
				"envelope": 214.9
			},
			{
				"t": 1.94,
				"current": 182,
				"envelope": 205.8
			},
			{
				"t": 1.96,
				"current": 170,
				"envelope": 196.6
			},
			{
				"t": 1.98,
				"current": 153,
				"envelope": 187.5
			},
			{
				"t": 2,
				"current": 144,
				"envelope": 178.7
			},
			{
				"t": 2.02,
				"current": 132,
				"envelope": 170.8
			},
			{
				"t": 2.04,
				"current": 118,
				"envelope": 162.9
			},
			{
				"t": 2.06,
				"current": 97,
				"envelope": 155
			},
			{
				"t": 2.08,
				"current": 79,
				"envelope": 143.4
			},
			{
				"t": 2.1,
				"current": 62,
				"envelope": 126.6
			},
			{
				"t": 2.12,
				"current": 50,
				"envelope": 109.8
			},
			{
				"t": 2.14,
				"current": 35,
				"envelope": 93
			},
			{
				"t": 2.16,
				"current": 18,
				"envelope": 77.2
			},
			{
				"t": 2.18,
				"current": 9,
				"envelope": 62.1
			},
			{
				"t": 2.2,
				"current": 3,
				"envelope": 47
			},
			{
				"t": 2.22,
				"current": 0,
				"envelope": 31.8
			},
			{
				"t": 2.24,
				"current": 0,
				"envelope": 22.5
			},
			{
				"t": 2.26,
				"current": 0,
				"envelope": 15.3
			},
			{
				"t": 2.28,
				"current": 0,
				"envelope": 8
			},
			{
				"t": 2.3,
				"current": 0,
				"envelope": .7
			},
			{
				"t": 2.32,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.34,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.36,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.38,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.4,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.42,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.44,
				"current": 0,
				"envelope": 0
			},
			{
				"t": 2.46,
				"current": 0,
				"envelope": 2.1
			},
			{
				"t": 2.48,
				"current": 18,
				"envelope": 11.7
			},
			{
				"t": 2.5,
				"current": 41,
				"envelope": 21.2
			},
			{
				"t": 2.52,
				"current": 68,
				"envelope": 30.7
			},
			{
				"t": 2.54,
				"current": 106,
				"envelope": 48.4
			},
			{
				"t": 2.56,
				"current": 138,
				"envelope": 79.1
			},
			{
				"t": 2.58,
				"current": 159,
				"envelope": 109.8
			},
			{
				"t": 2.6,
				"current": 209,
				"envelope": 140.4
			},
			{
				"t": 2.62,
				"current": 276,
				"envelope": 178.6
			},
			{
				"t": 2.64,
				"current": 317,
				"envelope": 222.9
			},
			{
				"t": 2.66,
				"current": 347,
				"envelope": 267.2
			},
			{
				"t": 2.68,
				"current": 373,
				"envelope": 311.5
			},
			{
				"t": 2.7,
				"current": 394,
				"envelope": 334.4
			},
			{
				"t": 2.72,
				"current": 397,
				"envelope": 348.7
			},
			{
				"t": 2.74,
				"current": 388,
				"envelope": 363
			},
			{
				"t": 2.76,
				"current": 376,
				"envelope": 377.3
			},
			{
				"t": 2.78,
				"current": 376,
				"envelope": 380.5
			},
			{
				"t": 2.8,
				"current": 356,
				"envelope": 382.1
			},
			{
				"t": 2.82,
				"current": 317,
				"envelope": 383.7
			},
			{
				"t": 2.84,
				"current": 288,
				"envelope": 384.8
			},
			{
				"t": 2.86,
				"current": 267,
				"envelope": 373.1
			},
			{
				"t": 2.88,
				"current": 259,
				"envelope": 361.5
			},
			{
				"t": 2.9,
				"current": 253,
				"envelope": 349.8
			},
			{
				"t": 2.92,
				"current": 256,
				"envelope": 335.8
			},
			{
				"t": 2.94,
				"current": 267,
				"envelope": 312.4
			},
			{
				"t": 2.96,
				"current": 273,
				"envelope": 288.9
			},
			{
				"t": 2.98,
				"current": 282,
				"envelope": 265.5
			},
			{
				"t": 3,
				"current": 291,
				"envelope": 253.2
			},
			{
				"t": 3.02,
				"current": 300,
				"envelope": 260.2
			},
			{
				"t": 3.04,
				"current": 300,
				"envelope": 267.1
			},
			{
				"t": 3.06,
				"current": 300,
				"envelope": 274.1
			},
			{
				"t": 3.08,
				"current": 300,
				"envelope": 279.3
			},
			{
				"t": 3.1,
				"current": 300,
				"envelope": 282.9
			},
			{
				"t": 3.12,
				"current": 309,
				"envelope": 286.5
			},
			{
				"t": 3.14,
				"current": 317,
				"envelope": 290.1
			},
			{
				"t": 3.16,
				"current": 329,
				"envelope": 295
			},
			{
				"t": 3.18,
				"current": 335,
				"envelope": 300.5
			},
			{
				"t": 3.2,
				"current": 341,
				"envelope": 306
			},
			{
				"t": 3.22,
				"current": 338,
				"envelope": 311.5
			},
			{
				"t": 3.24,
				"current": 335,
				"envelope": 314.7
			},
			{
				"t": 3.26,
				"current": 332,
				"envelope": 317.5
			},
			{
				"t": 3.28,
				"current": 326,
				"envelope": 320.3
			},
			{
				"t": 3.3,
				"current": 317,
				"envelope": 324.7
			},
			{
				"t": 3.32,
				"current": 317,
				"envelope": 405
			},
			{
				"t": 3.34,
				"current": 347,
				"envelope": 485.2
			},
			{
				"t": 3.36,
				"current": 544,
				"envelope": 565.5
			},
			{
				"t": 3.38,
				"current": 1029,
				"envelope": 687.1
			},
			{
				"t": 3.4,
				"current": 1587,
				"envelope": 992.7
			},
			{
				"t": 3.42,
				"current": 1740,
				"envelope": 1298.3
			},
			{
				"t": 3.44,
				"current": 1717,
				"envelope": 1603.9
			},
			{
				"t": 3.46,
				"current": 2084,
				"envelope": 1829.1
			},
			{
				"t": 3.48,
				"current": 2084,
				"envelope": 1902.8
			},
			{
				"t": 3.5,
				"current": 1708,
				"envelope": 1976.5
			},
			{
				"t": 3.52,
				"current": 1658,
				"envelope": 2050.3
			},
			{
				"t": 3.54,
				"current": 1755,
				"envelope": 2072.4
			},
			{
				"t": 3.56,
				"current": 1846,
				"envelope": 2045
			},
			{
				"t": 3.58,
				"current": 1896,
				"envelope": 2017.5
			},
			{
				"t": 3.6,
				"current": 1925,
				"envelope": 1990.1
			},
			{
				"t": 3.62,
				"current": 1946,
				"envelope": 1984.8
			},
			{
				"t": 3.64,
				"current": 1958,
				"envelope": 1990.3
			},
			{
				"t": 3.66,
				"current": 1969,
				"envelope": 1995.7
			},
			{
				"t": 3.68,
				"current": 1981,
				"envelope": 2001.1
			},
			{
				"t": 3.7,
				"current": 1987,
				"envelope": 2002.7
			},
			{
				"t": 3.72,
				"current": 1987,
				"envelope": 2003.5
			},
			{
				"t": 3.74,
				"current": 1993,
				"envelope": 2004.2
			},
			{
				"t": 3.76,
				"current": 1993,
				"envelope": 2005
			}
		],
		"reason": "Motor current stays within the Normal envelope for 50% of the close cycle, so no elevated-effort interval was isolated. A Normal prediction is not a safety clearance."
	}
}] }.rows.find((r) => r.prediction !== "Normal");
console.log(renderToStaticMarkup(/* @__PURE__ */ jsx(DoorTrace, {
	trace: bad.evidence.trace,
	regions: bad.evidence.regions,
	status: bad.prediction,
	startClock: bad.evidence.start_clock
})));
//#endregion
export {};
