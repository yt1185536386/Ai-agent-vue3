/**
 * echarts 按需注册(全量引入约 1MB,按需后仅打包实际用到的部分)。
 * 统一从这里导入 echarts,不要直接 `import * as echarts from 'echarts'`。
 * 当前项目只用:折线图 / 柱状图 + 提示框 / 图例 / 网格坐标系。
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ComposeOption } from 'echarts/core'
import type { BarSeriesOption, LineSeriesOption } from 'echarts/charts'
import type {
  GridComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
} from 'echarts/components'

echarts.use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer,
])

/** 与已注册图表/组件组合后的 option 类型(等价于全量包的 EChartsOption) */
export type EChartsOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
>

/** 图表实例类型 */
export type ECharts = ReturnType<typeof echarts.init>

export default echarts
