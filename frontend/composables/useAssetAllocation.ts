export type AllocationDriftRow = {
  assetClass: string
  label: string
  targetPercentage: number
  actualPercentage: number
  actualAmount: number
  driftPp: number
}

export type UntaggedInvestment = {
  id: number
  name: string
  kind: string
}

export type TaggableAccount = {
  id: number
  name: string
  type: string
}

type AllocationData = {
  drift: AllocationDriftRow[]
  untaggedInvestments: UntaggedInvestment[]
  taggableCashAccounts: TaggableAccount[]
}

const ALLOCATION_QUERY = `{
  portfolioAllocationDrift { assetClass label targetPercentage actualPercentage actualAmount driftPp }
  untaggedInvestments { id name kind }
  taggableCashAccounts { id name type }
}`

const EMPTY: AllocationData = { drift: [], untaggedInvestments: [], taggableCashAccounts: [] }

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
        untaggedInvestments: res?.data?.untaggedInvestments ?? [],
        taggableCashAccounts: res?.data?.taggableCashAccounts ?? [],
      }
    },
    { default: () => EMPTY },
  )

  return { allocation, refresh }
}
