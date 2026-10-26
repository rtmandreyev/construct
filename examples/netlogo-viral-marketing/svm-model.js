// Simple Viral Marketing (Uri Wilensky, 2012; NetLogo IABM Textbook, chapter 8), re-implemented
// line by line from the NetLogo code so it can run in a browser. Same rules and parameters; a
// different random-number generator, so a seed here is not a NetLogo seed.
//
//   setup:  create-network (random: Erdos-Renyi, p = 0.004; preferential-attachment: Barabasi-Albert,
//           min-degree 1), then seed `budget` people (randomly, or the highest betweenness centrality)
//   go:     stop when everyone has adopted; otherwise ask every person who has not adopted, in random
//           order, to decide: with probability 0.01 adopt (advertising), else, if they have neighbours,
//           adopt with probability 0.5 x the share of their neighbours who have adopted; then tick
//
// The page and the Node check both load this file, so they run the same code.

(function (root) {
  const N = 500, P_LINK = 0.004, P_AD = 0.01, IMITATION = 0.5;

  // a small seedable generator (sfc32 from a 32-bit seed)
  function rng(seed) {
    let a = 0x9e3779b9, b = 0x243f6a88, c = 0xb7e15162, d = seed >>> 0;
    const next = () => {
      a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
      let t = (a + b) | 0; a = b ^ (b >>> 9); b = (c + (c << 3)) | 0;
      c = (c << 21) | (c >>> 11); d = (d + 1) | 0; t = (t + d) | 0; c = (c + t) | 0;
      return (t >>> 0) / 4294967296;
    };
    for (let i = 0; i < 16; i++) next();
    return next;
  }

  function shuffle(a, rand) {
    for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }

  function randomNetwork(rand) {           // nw:generate-random turtles links 500 0.004
    const links = [];
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) if (rand() < P_LINK) links.push([i, j]);
    return links;
  }

  function preferentialAttachment(rand) {  // nw:generate-preferential-attachment turtles links 500 1
    const links = [[0, 1]], ends = [0, 1];
    for (let v = 2; v < N; v++) {
      const u = ends[Math.floor(rand() * ends.length)];   // chosen with probability proportional to degree
      links.push([u, v]); ends.push(u, v);
    }
    return links;
  }

  function adjacency(links) {
    const adj = Array.from({ length: N }, () => []);
    for (const [a, b] of links) { adj[a].push(b); adj[b].push(a); }
    return adj;
  }

  function betweenness(adj) {              // Brandes (2001), unweighted and undirected
    const cb = new Float64Array(N), sigma = new Float64Array(N), dist = new Int32Array(N), delta = new Float64Array(N);
    const preds = Array.from({ length: N }, () => []), stack = new Int32Array(N), queue = new Int32Array(N);
    for (let s = 0; s < N; s++) {
      for (let i = 0; i < N; i++) { preds[i].length = 0; sigma[i] = 0; dist[i] = -1; delta[i] = 0; }
      sigma[s] = 1; dist[s] = 0;
      let qh = 0, qt = 0, sp = 0; queue[qt++] = s;
      while (qh < qt) {
        const v = queue[qh++]; stack[sp++] = v;
        for (const w of adj[v]) {
          if (dist[w] < 0) { dist[w] = dist[v] + 1; queue[qt++] = w; }
          if (dist[w] === dist[v] + 1) { sigma[w] += sigma[v]; preds[w].push(v); }
        }
      }
      while (sp > 0) {
        const w = stack[--sp];
        for (const v of preds[w]) delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w]);
        if (w !== s) cb[w] += delta[w];
      }
    }
    return cb;   // each pair counted from both ends; a constant factor, so the ranking is unchanged
  }

  // One whole run. Returns the network, who was seeded, and for every person the tick they
  // adopted, why (seed, ad or neighbour) and, for a neighbour adoption, one adopted neighbour
  // credited for drawing (chosen at random among the adopted neighbours, as a drawing choice).
  function run({ networkType = "random", seeding = "betweenness", budget = 1, seed = 1, maxTicks = 5000 } = {}) {
    const rand = rng(seed);
    const links = networkType === "preferential-attachment" ? preferentialAttachment(rand) : randomNetwork(rand);
    const adj = adjacency(links);
    const adopted = new Uint8Array(N), tick = new Int32Array(N).fill(-1), cause = new Array(N).fill(""), src = new Int32Array(N).fill(-1);
    let seeds;
    if (seeding === "random") {
      seeds = shuffle([...Array(N).keys()], rand).slice(0, budget);
    } else {                                 // max-n-of budget turtles [ nw:betweenness-centrality ], ties at random
      const cb = betweenness(adj);
      const order = shuffle([...Array(N).keys()], rand).sort((a, b) => cb[b] - cb[a]);
      seeds = order.slice(0, budget);
    }
    for (const s of seeds) { adopted[s] = 1; tick[s] = 0; cause[s] = "seed"; }
    let t = 0, count = seeds.length;
    const curve = [count];
    while (count < N && t < maxTicks) {
      const waiting = shuffle([...Array(N).keys()].filter((i) => !adopted[i]), rand);
      for (const i of waiting) {             // ask turtles with [ not adopted? ] [ decide-to-adopt ]
        if (rand() < P_AD) { adopted[i] = 1; tick[i] = t + 1; cause[i] = "ad"; count++; continue; }
        const nb = adj[i];
        if (nb.length) {
          let k = 0; for (const j of nb) k += adopted[j];
          if (rand() < IMITATION * (k / nb.length)) {
            adopted[i] = 1; tick[i] = t + 1; cause[i] = "neighbour"; count++;
            const on = nb.filter((j) => adopted[j] && j !== i && tick[j] <= t + 1 && cause[j] !== "" );
            src[i] = on[Math.floor(rand() * on.length)];
          }
        }
      }
      t++; curve.push(count);
    }
    return { n: N, links, adj, seeds, tick: Array.from(tick), cause, src: Array.from(src), curve, ticks: t };
  }

  // the first tick at which at least q of the people had adopted
  function firstTick(curve, q) {
    const need = Math.ceil(q * N);
    for (let t = 0; t < curve.length; t++) if (curve[t] >= need) return t;
    return null;
  }

  const api = { N, run, firstTick, rng };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.SVM = api;
})(typeof window !== "undefined" ? window : globalThis);
