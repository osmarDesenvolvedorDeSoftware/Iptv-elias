import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';

import type { ApiError } from '../data/adapters/ApiAdapter';
import { DualList, DualListHandle, DualListItem } from '../components/DualList';
import { getBouquets, saveBouquet } from '../data/services/bouquetService';
import { Bouquet, CatalogItem, CatalogItemType } from '../data/types';
import { useToast } from '../providers/ToastProvider';

type FilterType = 'all' | CatalogItemType;

type SelectionsMap = Record<number, string[]>;

type FiltersState = {
  search: string;
  type: FilterType;
};

function normalizeSelections(
  raw: Record<string, string[]>,
  bouquets: Bouquet[],
): SelectionsMap {
  return bouquets.reduce<SelectionsMap>((accumulator, bouquet) => {
    const selected = raw[String(bouquet.id)] ?? [];
    accumulator[bouquet.id] = [...selected];
    return accumulator;
  }, {});
}

function cloneSelections(selections: SelectionsMap): SelectionsMap {
  return Object.entries(selections).reduce<SelectionsMap>((accumulator, [id, items]) => {
    accumulator[Number(id)] = [...items];
    return accumulator;
  }, {});
}

function getItemMetadata(item: CatalogItem): string {
  if (item.type === 'movie') {
    return [`Filme`, item.year].filter(Boolean).join(' • ');
  }

  return [`Série`, `${item.seasons} temp.`, item.status].filter(Boolean).join(' • ');
}

export default function Bouquets() {
  const { push } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [bouquets, setBouquets] = useState<Bouquet[]>([]);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [selections, setSelections] = useState<SelectionsMap>({});
  const [originalSelections, setOriginalSelections] = useState<SelectionsMap>({});
  const [activeBouquetId, setActiveBouquetId] = useState<number | null>(null);
  const [filters, setFilters] = useState<FiltersState>({ search: '', type: 'all' });
  const [availableSelection, setAvailableSelection] = useState<Set<string>>(new Set());
  const [bouquetSelection, setBouquetSelection] = useState<Set<string>>(new Set());
  const availableListRef = useRef<DualListHandle>(null);
  const selectedListRef = useRef<DualListHandle>(null);
  const actionButtonRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    setAvailableSelection(new Set());
    setBouquetSelection(new Set());
  }, [activeBouquetId]);

  useEffect(() => {
    if (!loading && activeBouquetId) {
      availableListRef.current?.focusFirst();
    }
  }, [activeBouquetId, loading]);

  const catalogMap = useMemo(() => {
    const map = new Map<string, CatalogItem>();
    catalog.forEach((item) => {
      map.set(item.id, item);
    });
    return map;
  }, [catalog]);

  const catalogOrder = useMemo(() => {
    const order = new Map<string, number>();
    catalog.forEach((item, index) => {
      order.set(item.id, index);
    });
    return order;
  }, [catalog]);

  const activeSelection = useMemo(() => {
    if (!activeBouquetId) {
      return [] as string[];
    }

    return selections[activeBouquetId] ?? [];
  }, [activeBouquetId, selections]);

  const availableItems = useMemo(() => {
    if (!activeBouquetId) {
      return [] as CatalogItem[];
    }

    const selectedIds = new Set(activeSelection);
    return catalog
      .filter((item) => !selectedIds.has(item.id))
      .sort((a, b) => a.title.localeCompare(b.title, 'pt-BR'));
  }, [activeBouquetId, activeSelection, catalog]);

  const filteredAvailableItems = useMemo(() => {
    return availableItems.filter((item) => {
      if (filters.type !== 'all' && item.type !== filters.type) {
        return false;
      }

      if (!filters.search) {
        return true;
      }

      const query = filters.search.toLowerCase();
      return item.title.toLowerCase().includes(query);
    });
  }, [availableItems, filters]);

  const selectedItems = useMemo(() => {
    if (!activeBouquetId) {
      return [] as CatalogItem[];
    }

    return (selections[activeBouquetId] ?? [])
      .map((id) => catalogMap.get(id))
      .filter(Boolean) as CatalogItem[];
  }, [activeBouquetId, catalogMap, selections]);

  const availableListItems = useMemo<DualListItem[]>(
    () =>
      filteredAvailableItems.map((item) => ({
        id: item.id,
        title: item.title,
        meta: getItemMetadata(item),
        badgeLabel: item.type === 'movie' ? 'Filme' : 'Série',
        badgeTone: 'accent',
      })),
    [filteredAvailableItems],
  );

  const selectedListItems = useMemo<DualListItem[]>(
    () =>
      selectedItems.map((item, index) => ({
        id: item.id,
        title: item.title,
        meta: getItemMetadata(item),
        badgeLabel: `#${index + 1}`,
        badgeTone: 'primary',
      })),
    [selectedItems],
  );

  const activeBouquet = useMemo(
    () => bouquets.find((bouquet) => bouquet.id === activeBouquetId) ?? null,
    [activeBouquetId, bouquets],
  );

  const hasUnsavedChanges = useMemo(() => {
    if (!activeBouquetId) {
      return false;
    }

    const current = selections[activeBouquetId] ?? [];
    const original = originalSelections[activeBouquetId] ?? [];

    if (current.length !== original.length) {
      return true;
    }

    return current.some((value, index) => value !== original[index]);
  }, [activeBouquetId, originalSelections, selections]);

  async function loadData() {
    setLoading(true);
    setError(null);

    try {
      const response = await getBouquets();
      setBouquets(response.bouquets);
      setCatalog(response.catalog);

      const normalized = normalizeSelections(response.selected, response.bouquets);
      setSelections(normalized);
      setOriginalSelections(cloneSelections(normalized));

      const firstBouquet = response.bouquets[0]?.id ?? null;
      setActiveBouquetId(firstBouquet);
    } catch (loadError) {
      const apiError = loadError as ApiError;
      setError(apiError?.message ?? 'Não foi possível carregar os dados de bouquets.');
    } finally {
      setLoading(false);
    }
  }

  function toggleAvailable(itemId: string) {
    setAvailableSelection((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function toggleBouquetSelection(itemId: string) {
    setBouquetSelection((current) => {
      const next = new Set(current);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function updateSelectionForBouquet(bouquetId: number, items: string[]) {
    setSelections((current) => ({
      ...current,
      [bouquetId]: items,
    }));
  }

  function handleMoveSelectedToBouquet() {
    if (!activeBouquetId || availableSelection.size === 0) {
      return;
    }

    const current = selections[activeBouquetId] ?? [];
    const orderedIds = Array.from(availableSelection).sort((a, b) => {
      const orderA = catalogOrder.get(a) ?? 0;
      const orderB = catalogOrder.get(b) ?? 0;
      return orderA - orderB;
    });

    const next = [...current];
    orderedIds.forEach((id) => {
      if (!next.includes(id)) {
        next.push(id);
      }
    });

    updateSelectionForBouquet(activeBouquetId, next);
    setAvailableSelection(new Set());
  }

  function handleMoveAllToBouquet() {
    if (!activeBouquetId) {
      return;
    }

    const current = selections[activeBouquetId] ?? [];
    const next = [...current];

    filteredAvailableItems.forEach((item) => {
      if (!next.includes(item.id)) {
        next.push(item.id);
      }
    });

    updateSelectionForBouquet(activeBouquetId, next);
    setAvailableSelection(new Set());
  }

  function handleRemoveSelectedFromBouquet() {
    if (!activeBouquetId || bouquetSelection.size === 0) {
      return;
    }

    const current = selections[activeBouquetId] ?? [];
    const idsToRemove = new Set(bouquetSelection);
    const next = current.filter((id) => !idsToRemove.has(id));

    updateSelectionForBouquet(activeBouquetId, next);
    setBouquetSelection(new Set());
  }

  function handleRemoveAllFromBouquet() {
    if (!activeBouquetId) {
      return;
    }

    updateSelectionForBouquet(activeBouquetId, []);
    setBouquetSelection(new Set());
  }

  function handleMove(direction: 'up' | 'down') {
    if (!activeBouquetId || bouquetSelection.size !== 1) {
      return;
    }

    const targetId = Array.from(bouquetSelection)[0];
    const current = selections[activeBouquetId] ?? [];
    const index = current.indexOf(targetId);

    if (index === -1) {
      return;
    }

    if (direction === 'up' && index > 0) {
      const next = [...current];
      [next[index - 1], next[index]] = [next[index], next[index - 1]];
      updateSelectionForBouquet(activeBouquetId, next);
    } else if (direction === 'down' && index < current.length - 1) {
      const next = [...current];
      [next[index + 1], next[index]] = [next[index], next[index + 1]];
      updateSelectionForBouquet(activeBouquetId, next);
    }
  }

  async function handleSave() {
    if (!activeBouquetId) {
      return;
    }

    setSaving(true);

    try {
      await saveBouquet(activeBouquetId, selections[activeBouquetId] ?? []);
      setOriginalSelections(cloneSelections(selections));
      push('Bouquet salvo com sucesso', 'success');
    } catch (saveError) {
      const apiError = saveError as ApiError;
      push(apiError?.message ?? 'Falha ao salvar o bouquet.', 'error');
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setSelections(cloneSelections(originalSelections));
    setAvailableSelection(new Set());
    setBouquetSelection(new Set());
    setFilters({ search: '', type: 'all' });
  }

  function handleFilterChange(event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = event.target;

    if (name === 'type') {
      setFilters((current) => ({ ...current, type: value as FilterType }));
    } else if (name === 'search') {
      setFilters((current) => ({ ...current, search: value }));
    }
  }

  function setActionButtonRef(index: number) {
    return (element: HTMLButtonElement | null) => {
      actionButtonRefs.current[index] = element;
    };
  }

  function focusActionButton(index: number) {
    actionButtonRefs.current[index]?.focus();
  }

  function focusAvailableList() {
    if (availableListItems.length > 0) {
      availableListRef.current?.focusFirst();
    } else {
      focusActionButton(2);
    }
  }

  function focusSelectedList() {
    if (selectedListItems.length > 0) {
      selectedListRef.current?.focusFirst();
    } else {
      focusActionButton(0);
    }
  }

  if (loading) {
    return (
      <section className="container-fluid py-4" aria-busy="true">
        <header className="d-flex flex-column align-items-center mb-4 text-center">
          <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
            Dashboard / Bouquets
          </nav>
          <h1 className="display-6 mb-0">Bouquets</h1>
        </header>
        <div className="d-flex align-items-center justify-content-center gap-2 mt-4">
          <span className="spinner-border spinner-border-sm" aria-hidden="true" />
          <span>Carregando catálogos…</span>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="container-fluid py-4" aria-live="polite">
        <header className="d-flex flex-column align-items-center mb-4 text-center">
          <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
            Dashboard / Bouquets
          </nav>
          <h1 className="display-6 mb-0">Bouquets</h1>
        </header>
        <div className="alert alert-danger d-flex flex-column flex-md-row align-items-md-center justify-content-between" role="alert">
          <span>{error}</span>
          <button type="button" className="btn btn-outline-light mt-3 mt-md-0" onClick={loadData}>
            Tentar novamente
          </button>
        </div>
      </section>
    );
  }

  if (!activeBouquet) {
    return (
      <section className="container-fluid py-4">
        <header className="d-flex flex-column align-items-center mb-4 text-center">
          <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
            Dashboard / Bouquets
          </nav>
          <h1 className="display-6 mb-0">Bouquets</h1>
        </header>
        <div className="alert alert-info" role="alert">
          Nenhum bouquet foi cadastrado nos mocks.
        </div>
      </section>
    );
  }

  return (
    <section className="container-fluid py-4">
      <header className="d-flex flex-column align-items-center mb-4 text-center">
        <nav className="text-uppercase text-muted small mb-2" aria-label="breadcrumb">
          Dashboard / Bouquets
        </nav>
        <h1 className="display-6 mb-0">Bouquets</h1>
      </header>

      <div className="card shadow-sm">
        <div className="card-header d-flex flex-column flex-lg-row gap-3 align-items-lg-end justify-content-between">
          <div>
            <h2 className="h5 mb-1">Gerenciar bouquet</h2>
            <p className="text-muted mb-0">Monte a grade do bouquet selecionado movendo itens entre as listas.</p>
          </div>
          <div className="d-flex flex-column flex-md-row gap-3 w-100 w-lg-auto">
            <div className="flex-fill">
              <label htmlFor="bouquet-select" className="form-label text-uppercase small text-muted">
                Bouquet
              </label>
              <select
                id="bouquet-select"
                className="form-control"
                value={activeBouquetId ?? ''}
                onChange={(event) => setActiveBouquetId(Number(event.target.value))}
              >
                {bouquets.map((bouquet) => (
                  <option key={bouquet.id} value={bouquet.id}>
                    {bouquet.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-fill">
              <label htmlFor="catalog-search" className="form-label text-uppercase small text-muted">
                Buscar no catálogo
              </label>
              <input
                id="catalog-search"
                type="search"
                className="form-control"
                placeholder="Título ou palavra-chave"
                name="search"
                value={filters.search}
                onChange={handleFilterChange}
              />
            </div>
            <div className="flex-fill flex-md-grow-0" style={{ minWidth: '12rem' }}>
              <label htmlFor="catalog-type" className="form-label text-uppercase small text-muted">
                Tipo
              </label>
              <select
                id="catalog-type"
                className="form-control"
                name="type"
                value={filters.type}
                onChange={handleFilterChange}
              >
                <option value="all">Filmes e Séries</option>
                <option value="movie">Somente Filmes</option>
                <option value="series">Somente Séries</option>
              </select>
            </div>
          </div>
        </div>

        <div className="card-body">
          <div className="row g-4 align-items-stretch">
            <div className="col-12 col-lg-5">
              <DualList
                ref={availableListRef}
                headingId="dual-list-available"
                heading="Disponíveis"
                badgeCount={filteredAvailableItems.length}
                items={availableListItems}
                selection={availableSelection}
                emptyMessage={
                  filters.search
                    ? 'Nenhum item corresponde aos filtros.'
                    : 'Nenhum item disponível no catálogo para mover.'
                }
                onToggle={toggleAvailable}
                orientation="left"
                onRequestFocusSwap={(direction) => {
                  if (direction === 'next') {
                    if (bouquetSelection.size > 0 || selectedListItems.length > 0) {
                      focusSelectedList();
                    } else {
                      focusActionButton(0);
                    }
                  }
                }}
              />
            </div>

            <div className="col-12 col-lg-2 d-flex flex-lg-column align-items-center justify-content-center gap-2">
              <button
                type="button"
                className="btn btn-outline-primary w-100"
                onClick={handleMoveSelectedToBouquet}
                disabled={availableSelection.size === 0}
                aria-label="Mover itens selecionados para o bouquet"
                ref={setActionButtonRef(0)}
              >
                &gt;
              </button>
              <button
                type="button"
                className="btn btn-outline-primary w-100"
                onClick={handleMoveAllToBouquet}
                disabled={filteredAvailableItems.length === 0}
                aria-label="Mover todos os itens filtrados para o bouquet"
                ref={setActionButtonRef(1)}
              >
                &gt;&gt;
              </button>
              <button
                type="button"
                className="btn btn-outline-primary w-100"
                onClick={handleRemoveSelectedFromBouquet}
                disabled={bouquetSelection.size === 0}
                aria-label="Remover itens selecionados do bouquet"
                ref={setActionButtonRef(2)}
              >
                &lt;
              </button>
              <button
                type="button"
                className="btn btn-outline-primary w-100"
                onClick={handleRemoveAllFromBouquet}
                disabled={selectedItems.length === 0}
                aria-label="Remover todos os itens do bouquet"
                ref={setActionButtonRef(3)}
              >
                &lt;&lt;
              </button>
            </div>

            <div className="col-12 col-lg-5">
              <DualList
                ref={selectedListRef}
                headingId="dual-list-selected"
                heading={`No bouquet (${activeBouquet.name})`}
                badgeCount={selectedItems.length}
                items={selectedListItems}
                selection={bouquetSelection}
                emptyMessage="Nenhum conteúdo adicionado a este bouquet."
                onToggle={toggleBouquetSelection}
                orientation="right"
                headingAdornment={
                  <div className="btn-group btn-group-sm" role="group" aria-label="Reordenar itens">
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => handleMove('up')}
                      disabled={bouquetSelection.size !== 1}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => handleMove('down')}
                      disabled={bouquetSelection.size !== 1}
                    >
                      ↓
                    </button>
                  </div>
                }
                onRequestFocusSwap={(direction) => {
                  if (direction === 'previous') {
                    focusAvailableList();
                  } else if (direction === 'next') {
                    focusActionButton(2);
                  }
                }}
              />
            </div>
          </div>
        </div>

        <div className="card-footer d-flex flex-column flex-md-row justify-content-end gap-2">
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={handleCancel}
            disabled={!hasUnsavedChanges || saving}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={!hasUnsavedChanges || saving}
          >
            {saving ? (
              <span className="d-inline-flex align-items-center gap-2">
                <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                Salvando…
              </span>
            ) : (
              'Salvar alterações'
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
