import {
  ForwardedRef,
  KeyboardEvent,
  ReactNode,
  forwardRef,
  memo,
  useImperativeHandle,
  useMemo,
  useRef,
} from 'react';

export interface DualListItem {
  id: string;
  title: string;
  meta?: string;
  badgeLabel?: string;
  badgeTone?: 'neutral' | 'primary' | 'accent' | 'info';
  endAdornment?: ReactNode;
}

export interface DualListHandle {
  focusFirst: () => void;
  focusLast: () => void;
}

interface DualListProps {
  headingId: string;
  heading: string;
  badgeCount?: number;
  headingAdornment?: ReactNode;
  items: DualListItem[];
  selection: Set<string>;
  emptyMessage: string;
  onToggle: (id: string) => void;
  orientation: 'left' | 'right';
  ariaDescription?: string;
  onRequestFocusSwap?: (direction: 'previous' | 'next') => void;
}

const badgeToneToClass: Record<NonNullable<DualListItem['badgeTone']>, string> = {
  neutral: 'badge bg-secondary text-uppercase',
  primary: 'badge bg-primary',
  accent: 'badge bg-dark text-uppercase',
  info: 'badge bg-info text-uppercase',
};

function DualListComponent(
  {
    headingId,
    heading,
    badgeCount,
    headingAdornment,
    items,
    selection,
    emptyMessage,
    onToggle,
    orientation,
    ariaDescription,
    onRequestFocusSwap,
  }: DualListProps,
  ref: ForwardedRef<DualListHandle>,
) {
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());
  const orderedIds = useMemo(() => items.map((item) => item.id), [items]);

  useImperativeHandle(
    ref,
    () => ({
      focusFirst: () => {
        const firstId = orderedIds[0];
        if (firstId) {
          itemRefs.current.get(firstId)?.focus();
        }
      },
      focusLast: () => {
        const lastId = orderedIds[orderedIds.length - 1];
        if (lastId) {
          itemRefs.current.get(lastId)?.focus();
        }
      },
    }),
    [orderedIds],
  );

  const setItemRef = (itemId: string) => (element: HTMLButtonElement | null) => {
    if (!element) {
      itemRefs.current.delete(itemId);
      return;
    }

    itemRefs.current.set(itemId, element);
  };

  function focusByIndex(index: number) {
    const targetId = orderedIds[index];
    if (typeof targetId === 'undefined') {
      return;
    }

    itemRefs.current.get(targetId)?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, itemId: string) {
    const index = orderedIds.indexOf(itemId);

    if (index === -1) {
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      const nextIndex = Math.min(orderedIds.length - 1, index + 1);
      focusByIndex(nextIndex);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      const previousIndex = Math.max(0, index - 1);
      focusByIndex(previousIndex);
    } else if (event.key === 'Home') {
      event.preventDefault();
      focusByIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      focusByIndex(orderedIds.length - 1);
    } else if (event.key === 'ArrowLeft' && orientation === 'right') {
      event.preventDefault();
      onRequestFocusSwap?.('previous');
    } else if (event.key === 'ArrowRight' && orientation === 'left') {
      event.preventDefault();
      onRequestFocusSwap?.('next');
    }
  }

  return (
    <div className="dual-list" aria-live="polite">
      <div className="dual-list__header">
        <div className="d-flex align-items-center gap-2">
          <h3 id={headingId} className="h6 mb-0">
            {heading}
          </h3>
          {typeof badgeCount === 'number' ? <span className="badge bg-secondary">{badgeCount}</span> : null}
        </div>
        {headingAdornment}
      </div>

      <div className="dual-list__items" role="region" aria-labelledby={headingId} aria-describedby={ariaDescription}>
        {items.length === 0 ? (
          <div className="p-4 text-center text-muted" role="status">
            {emptyMessage}
          </div>
        ) : (
          <div
            className="dual-list__scroll"
            role="listbox"
            aria-multiselectable="true"
            aria-labelledby={headingId}
            aria-describedby={ariaDescription}
          >
            {items.map((item, index) => {
              const isSelected = selection.has(item.id);
              const badgeClass = item.badgeTone ? badgeToneToClass[item.badgeTone] : 'badge bg-secondary';

              return (
                <button
                  key={item.id}
                  ref={setItemRef(item.id)}
                  type="button"
                  className="dual-list__item"
                  onClick={() => onToggle(item.id)}
                  onKeyDown={(event) => handleKeyDown(event, item.id)}
                  aria-pressed={isSelected}
                  aria-selected={isSelected}
                  role="option"
                  tabIndex={0}
                  data-index={index}
                >
                  <span>
                    <span className="dual-list__title">{item.title}</span>
                    {item.meta ? <span className="dual-list__meta d-block">{item.meta}</span> : null}
                  </span>
                  <span className="d-inline-flex align-items-center gap-2">
                    {item.endAdornment}
                    {item.badgeLabel ? <span className={badgeClass}>{item.badgeLabel}</span> : null}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export const DualList = memo(forwardRef<DualListHandle, DualListProps>(DualListComponent));
