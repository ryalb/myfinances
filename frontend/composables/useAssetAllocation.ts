export type AllocationDriftRow = {
  assetClass: string
  label: string
  targetPercentage: number
  actualPercentage: number
  actualAmount: number
  driftPp: number
}

export type ReclassifiableInvestment = {
  id: number
  name: string
  kind: string
  assetClass: string
  tagId: number | null
}

export type TaggableAccount = {
  id: number
  name: string
  type: string
  tagId: number | null
}

type AllocationData = {
  drift: AllocationDriftRow[]
  reclassifiableInvestments: ReclassifiableInvestment[]
  taggableCashAccounts: TaggableAccount[]
}

const ALLOCATION_QUERY = `{
  portfolioAllocationDrift { assetClass label targetPercentage actualPercentage actualAmount driftPp }
  reclassifiableInvestments { id name kind assetClass tagId }
  taggableCashAccounts { id name type tagId }
}`

const EMPTY: AllocationData = { drift: [], reclassifiableInvestments: [], taggableCashAccounts: [] }

export function useAssetAllocation() {
  const { graphql } = useApi()

  const { data: allocation, refresh } = useAsyncData<AllocationData>(
    'asset-allocation',
    async () => {
      const res = await graphql<{ data?: Partial<AllocationData> & { portfolioAllocationDrift?: AllocationDriftRow[] } }>(
        ALLOCATION_QUERY,
      )
      return {
        drift: res?.data?.portfolioAllocationDrift ?? [],
        reclassifiableInvestments: res?.data?.reclassifiableInvestments ?? [],
        taggableCashAccounts: res?.data?.taggableCashAccounts ?? [],
      }
    },
    { default: () => EMPTY },
  )

  return { allocation, refresh }
}
