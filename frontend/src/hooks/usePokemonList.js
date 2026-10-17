import { useQuery } from '@tanstack/react-query'
import { listPokemon } from '@/api/pokemon'

export function usePokemonList(filters) {
  return useQuery({
    queryKey: ['pokemon', filters],
    queryFn: () => listPokemon(filters),
    keepPreviousData: true,
    staleTime: 30_000,
  })
}
