import { type NodeTypes } from '@xyflow/react'
import { FluidNode } from './FluidNode'

export const nodeTypes: NodeTypes = {
  fluid: FluidNode as NodeTypes['fluid'],
}
