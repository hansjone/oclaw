'use strict'

/******************************************************************************
 * Vendored dijkstrajs (MIT, Wyatt Baldwin / tcort)
 * https://github.com/tcort/dijkstrajs
 *
 * 原本通过 node_modules 中的 dijkstrajs 包提供；插件打包部署时不会携带
 * node_modules，导致 qrcode 库加载失败。这里内建为普通源码文件，
 * 使 qrcode-lib 在任何部署方式下都零外部依赖可用。
 *****************************************************************************/
var dijkstra = {
  single_source_shortest_paths: function (graph, s, d) {
    // Predecessor map for each node that has been encountered.
    // node ID => predecessor node ID
    var predecessors = {}

    // Costs of shortest paths from s to all nodes encountered.
    // node ID => cost
    var costs = {}
    costs[s] = 0

    var open = dijkstra.PriorityQueue.make()
    open.push(s, 0)

    var closest,
      u, v,
      costOfSToU,
      adjacentNodes,
      costOfE,
      costOfSToUPlusCostOfE,
      costOfSToV,
      firstVisit
    while (!open.empty()) {
      closest = open.pop()
      u = closest.value
      costOfSToU = closest.cost

      adjacentNodes = graph[u] || {}

      for (v in adjacentNodes) {
        if (adjacentNodes.hasOwnProperty(v)) {
          costOfE = adjacentNodes[v]
          costOfSToUPlusCostOfE = costOfSToU + costOfE

          costOfSToV = costs[v]
          firstVisit = (typeof costs[v] === 'undefined')
          if (firstVisit || costOfSToV > costOfSToUPlusCostOfE) {
            costs[v] = costOfSToUPlusCostOfE
            open.push(v, costOfSToUPlusCostOfE)
            predecessors[v] = u
          }
        }
      }
    }

    if (typeof d !== 'undefined' && typeof costs[d] === 'undefined') {
      var msg = ['Could not find a path from ', s, ' to ', d, '.'].join('')
      throw new Error(msg)
    }

    return predecessors
  },

  extract_shortest_path_from_predecessor_list: function (predecessors, d) {
    var nodes = []
    var u = d
    var predecessor
    while (u) {
      nodes.push(u)
      predecessor = predecessors[u]
      u = predecessors[u]
    }
    nodes.reverse()
    return nodes
  },

  find_path: function (graph, s, d) {
    var predecessors = dijkstra.single_source_shortest_paths(graph, s, d)
    return dijkstra.extract_shortest_path_from_predecessor_list(
      predecessors, d)
  },

  /**
   * A very naive priority queue implementation.
   */
  PriorityQueue: {
    make: function (opts) {
      var T = dijkstra.PriorityQueue
      var t = {}
      var key
      opts = opts || {}
      for (key in T) {
        if (T.hasOwnProperty(key)) {
          t[key] = T[key]
        }
      }
      t.queue = []
      t.sorter = opts.sorter || T.defaultSorter
      return t
    },

    defaultSorter: function (a, b) {
      return a.cost - b.cost
    },

    push: function (value, cost) {
      var item = { value: value, cost: cost }
      this.queue.push(item)
      this.queue.sort(this.sorter)
    },

    pop: function () {
      return this.queue.shift()
    },

    empty: function () {
      return this.queue.length === 0
    }
  }
}

module.exports = dijkstra
