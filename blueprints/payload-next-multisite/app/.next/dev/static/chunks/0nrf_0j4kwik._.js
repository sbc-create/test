(globalThis["TURBOPACK"] || (globalThis["TURBOPACK"] = [])).push([typeof document === "object" ? document.currentScript : undefined,
"[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/modifiers/dist/modifiers.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "createSnapModifier",
    ()=>createSnapModifier,
    "restrictToFirstScrollableAncestor",
    ()=>restrictToFirstScrollableAncestor,
    "restrictToHorizontalAxis",
    ()=>restrictToHorizontalAxis,
    "restrictToParentElement",
    ()=>restrictToParentElement,
    "restrictToVerticalAxis",
    ()=>restrictToVerticalAxis,
    "restrictToWindowEdges",
    ()=>restrictToWindowEdges,
    "snapCenterToCursor",
    ()=>snapCenterToCursor
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/utilities/dist/utilities.esm.js [app-client] (ecmascript)");
;
function createSnapModifier(gridSize) {
    return (_ref)=>{
        let { transform } = _ref;
        return {
            ...transform,
            x: Math.ceil(transform.x / gridSize) * gridSize,
            y: Math.ceil(transform.y / gridSize) * gridSize
        };
    };
}
const restrictToHorizontalAxis = (_ref)=>{
    let { transform } = _ref;
    return {
        ...transform,
        y: 0
    };
};
function restrictToBoundingRect(transform, rect, boundingRect) {
    const value = {
        ...transform
    };
    if (rect.top + transform.y <= boundingRect.top) {
        value.y = boundingRect.top - rect.top;
    } else if (rect.bottom + transform.y >= boundingRect.top + boundingRect.height) {
        value.y = boundingRect.top + boundingRect.height - rect.bottom;
    }
    if (rect.left + transform.x <= boundingRect.left) {
        value.x = boundingRect.left - rect.left;
    } else if (rect.right + transform.x >= boundingRect.left + boundingRect.width) {
        value.x = boundingRect.left + boundingRect.width - rect.right;
    }
    return value;
}
const restrictToParentElement = (_ref)=>{
    let { containerNodeRect, draggingNodeRect, transform } = _ref;
    if (!draggingNodeRect || !containerNodeRect) {
        return transform;
    }
    return restrictToBoundingRect(transform, draggingNodeRect, containerNodeRect);
};
const restrictToFirstScrollableAncestor = (_ref)=>{
    let { draggingNodeRect, transform, scrollableAncestorRects } = _ref;
    const firstScrollableAncestorRect = scrollableAncestorRects[0];
    if (!draggingNodeRect || !firstScrollableAncestorRect) {
        return transform;
    }
    return restrictToBoundingRect(transform, draggingNodeRect, firstScrollableAncestorRect);
};
const restrictToVerticalAxis = (_ref)=>{
    let { transform } = _ref;
    return {
        ...transform,
        x: 0
    };
};
const restrictToWindowEdges = (_ref)=>{
    let { transform, draggingNodeRect, windowRect } = _ref;
    if (!draggingNodeRect || !windowRect) {
        return transform;
    }
    return restrictToBoundingRect(transform, draggingNodeRect, windowRect);
};
const snapCenterToCursor = (_ref)=>{
    let { activatorEvent, draggingNodeRect, transform } = _ref;
    if (draggingNodeRect && activatorEvent) {
        const activatorCoordinates = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getEventCoordinates"])(activatorEvent);
        if (!activatorCoordinates) {
            return transform;
        }
        const offsetX = activatorCoordinates.x - draggingNodeRect.left;
        const offsetY = activatorCoordinates.y - draggingNodeRect.top;
        return {
            ...transform,
            x: transform.x + offsetX - draggingNodeRect.width / 2,
            y: transform.y + offsetY - draggingNodeRect.height / 2
        };
    }
    return transform;
};
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/sortable/dist/sortable.esm.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "SortableContext",
    ()=>SortableContext,
    "arrayMove",
    ()=>arrayMove,
    "arraySwap",
    ()=>arraySwap,
    "defaultAnimateLayoutChanges",
    ()=>defaultAnimateLayoutChanges,
    "defaultNewIndexGetter",
    ()=>defaultNewIndexGetter,
    "hasSortableData",
    ()=>hasSortableData,
    "horizontalListSortingStrategy",
    ()=>horizontalListSortingStrategy,
    "rectSortingStrategy",
    ()=>rectSortingStrategy,
    "rectSwappingStrategy",
    ()=>rectSwappingStrategy,
    "sortableKeyboardCoordinates",
    ()=>sortableKeyboardCoordinates,
    "useSortable",
    ()=>useSortable,
    "verticalListSortingStrategy",
    ()=>verticalListSortingStrategy
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/core/dist/core.esm.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/utilities/dist/utilities.esm.js [app-client] (ecmascript)");
;
;
;
/**
 * Move an array item to a different position. Returns a new array with the item moved to the new position.
 */ function arrayMove(array, from, to) {
    const newArray = array.slice();
    newArray.splice(to < 0 ? newArray.length + to : to, 0, newArray.splice(from, 1)[0]);
    return newArray;
}
/**
 * Swap an array item to a different position. Returns a new array with the item swapped to the new position.
 */ function arraySwap(array, from, to) {
    const newArray = array.slice();
    newArray[from] = array[to];
    newArray[to] = array[from];
    return newArray;
}
function getSortedRects(items, rects) {
    return items.reduce((accumulator, id, index)=>{
        const rect = rects.get(id);
        if (rect) {
            accumulator[index] = rect;
        }
        return accumulator;
    }, Array(items.length));
}
function isValidIndex(index) {
    return index !== null && index >= 0;
}
function itemsEqual(a, b) {
    if (a === b) {
        return true;
    }
    if (a.length !== b.length) {
        return false;
    }
    for(let i = 0; i < a.length; i++){
        if (a[i] !== b[i]) {
            return false;
        }
    }
    return true;
}
function normalizeDisabled(disabled) {
    if (typeof disabled === 'boolean') {
        return {
            draggable: disabled,
            droppable: disabled
        };
    }
    return disabled;
}
// To-do: We should be calculating scale transformation
const defaultScale = {
    scaleX: 1,
    scaleY: 1
};
const horizontalListSortingStrategy = (_ref)=>{
    var _rects$activeIndex;
    let { rects, activeNodeRect: fallbackActiveRect, activeIndex, overIndex, index } = _ref;
    const activeNodeRect = (_rects$activeIndex = rects[activeIndex]) != null ? _rects$activeIndex : fallbackActiveRect;
    if (!activeNodeRect) {
        return null;
    }
    const itemGap = getItemGap(rects, index, activeIndex);
    if (index === activeIndex) {
        const newIndexRect = rects[overIndex];
        if (!newIndexRect) {
            return null;
        }
        return {
            x: activeIndex < overIndex ? newIndexRect.left + newIndexRect.width - (activeNodeRect.left + activeNodeRect.width) : newIndexRect.left - activeNodeRect.left,
            y: 0,
            ...defaultScale
        };
    }
    if (index > activeIndex && index <= overIndex) {
        return {
            x: -activeNodeRect.width - itemGap,
            y: 0,
            ...defaultScale
        };
    }
    if (index < activeIndex && index >= overIndex) {
        return {
            x: activeNodeRect.width + itemGap,
            y: 0,
            ...defaultScale
        };
    }
    return {
        x: 0,
        y: 0,
        ...defaultScale
    };
};
function getItemGap(rects, index, activeIndex) {
    const currentRect = rects[index];
    const previousRect = rects[index - 1];
    const nextRect = rects[index + 1];
    if (!currentRect || !previousRect && !nextRect) {
        return 0;
    }
    if (activeIndex < index) {
        return previousRect ? currentRect.left - (previousRect.left + previousRect.width) : nextRect.left - (currentRect.left + currentRect.width);
    }
    return nextRect ? nextRect.left - (currentRect.left + currentRect.width) : currentRect.left - (previousRect.left + previousRect.width);
}
const rectSortingStrategy = (_ref)=>{
    let { rects, activeIndex, overIndex, index } = _ref;
    const newRects = arrayMove(rects, overIndex, activeIndex);
    const oldRect = rects[index];
    const newRect = newRects[index];
    if (!newRect || !oldRect) {
        return null;
    }
    return {
        x: newRect.left - oldRect.left,
        y: newRect.top - oldRect.top,
        scaleX: newRect.width / oldRect.width,
        scaleY: newRect.height / oldRect.height
    };
};
const rectSwappingStrategy = (_ref)=>{
    let { activeIndex, index, rects, overIndex } = _ref;
    let oldRect;
    let newRect;
    if (index === activeIndex) {
        oldRect = rects[index];
        newRect = rects[overIndex];
    }
    if (index === overIndex) {
        oldRect = rects[index];
        newRect = rects[activeIndex];
    }
    if (!newRect || !oldRect) {
        return null;
    }
    return {
        x: newRect.left - oldRect.left,
        y: newRect.top - oldRect.top,
        scaleX: newRect.width / oldRect.width,
        scaleY: newRect.height / oldRect.height
    };
};
// To-do: We should be calculating scale transformation
const defaultScale$1 = {
    scaleX: 1,
    scaleY: 1
};
const verticalListSortingStrategy = (_ref)=>{
    var _rects$activeIndex;
    let { activeIndex, activeNodeRect: fallbackActiveRect, index, rects, overIndex } = _ref;
    const activeNodeRect = (_rects$activeIndex = rects[activeIndex]) != null ? _rects$activeIndex : fallbackActiveRect;
    if (!activeNodeRect) {
        return null;
    }
    if (index === activeIndex) {
        const overIndexRect = rects[overIndex];
        if (!overIndexRect) {
            return null;
        }
        return {
            x: 0,
            y: activeIndex < overIndex ? overIndexRect.top + overIndexRect.height - (activeNodeRect.top + activeNodeRect.height) : overIndexRect.top - activeNodeRect.top,
            ...defaultScale$1
        };
    }
    const itemGap = getItemGap$1(rects, index, activeIndex);
    if (index > activeIndex && index <= overIndex) {
        return {
            x: 0,
            y: -activeNodeRect.height - itemGap,
            ...defaultScale$1
        };
    }
    if (index < activeIndex && index >= overIndex) {
        return {
            x: 0,
            y: activeNodeRect.height + itemGap,
            ...defaultScale$1
        };
    }
    return {
        x: 0,
        y: 0,
        ...defaultScale$1
    };
};
function getItemGap$1(clientRects, index, activeIndex) {
    const currentRect = clientRects[index];
    const previousRect = clientRects[index - 1];
    const nextRect = clientRects[index + 1];
    if (!currentRect) {
        return 0;
    }
    if (activeIndex < index) {
        return previousRect ? currentRect.top - (previousRect.top + previousRect.height) : nextRect ? nextRect.top - (currentRect.top + currentRect.height) : 0;
    }
    return nextRect ? nextRect.top - (currentRect.top + currentRect.height) : previousRect ? currentRect.top - (previousRect.top + previousRect.height) : 0;
}
const ID_PREFIX = 'Sortable';
const Context = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createContext({
    activeIndex: -1,
    containerId: ID_PREFIX,
    disableTransforms: false,
    items: [],
    overIndex: -1,
    useDragOverlay: false,
    sortedRects: [],
    strategy: rectSortingStrategy,
    disabled: {
        draggable: false,
        droppable: false
    }
});
function SortableContext(_ref) {
    let { children, id, items: userDefinedItems, strategy = rectSortingStrategy, disabled: disabledProp = false } = _ref;
    const { active, dragOverlay, droppableRects, over, measureDroppableContainers } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDndContext"])();
    const containerId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useUniqueId"])(ID_PREFIX, id);
    const useDragOverlay = Boolean(dragOverlay.rect !== null);
    const items = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "SortableContext.useMemo[items]": ()=>userDefinedItems.map({
                "SortableContext.useMemo[items]": (item)=>typeof item === 'object' && 'id' in item ? item.id : item
            }["SortableContext.useMemo[items]"])
    }["SortableContext.useMemo[items]"], [
        userDefinedItems
    ]);
    const isDragging = active != null;
    const activeIndex = active ? items.indexOf(active.id) : -1;
    const overIndex = over ? items.indexOf(over.id) : -1;
    const previousItemsRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(items);
    const itemsHaveChanged = !itemsEqual(items, previousItemsRef.current);
    const disableTransforms = overIndex !== -1 && activeIndex === -1 || itemsHaveChanged;
    const disabled = normalizeDisabled(disabledProp);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useIsomorphicLayoutEffect"])({
        "SortableContext.useIsomorphicLayoutEffect": ()=>{
            if (itemsHaveChanged && isDragging) {
                measureDroppableContainers(items);
            }
        }
    }["SortableContext.useIsomorphicLayoutEffect"], [
        itemsHaveChanged,
        items,
        isDragging,
        measureDroppableContainers
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "SortableContext.useEffect": ()=>{
            previousItemsRef.current = items;
        }
    }["SortableContext.useEffect"], [
        items
    ]);
    const contextValue = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "SortableContext.useMemo[contextValue]": ()=>({
                activeIndex,
                containerId,
                disabled,
                disableTransforms,
                items,
                overIndex,
                useDragOverlay,
                sortedRects: getSortedRects(items, droppableRects),
                strategy
            })
    }["SortableContext.useMemo[contextValue]"], [
        activeIndex,
        containerId,
        disabled.draggable,
        disabled.droppable,
        disableTransforms,
        items,
        overIndex,
        droppableRects,
        useDragOverlay,
        strategy
    ]);
    return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(Context.Provider, {
        value: contextValue
    }, children);
}
const defaultNewIndexGetter = (_ref)=>{
    let { id, items, activeIndex, overIndex } = _ref;
    return arrayMove(items, activeIndex, overIndex).indexOf(id);
};
const defaultAnimateLayoutChanges = (_ref2)=>{
    let { containerId, isSorting, wasDragging, index, items, newIndex, previousItems, previousContainerId, transition } = _ref2;
    if (!transition || !wasDragging) {
        return false;
    }
    if (previousItems !== items && index === newIndex) {
        return false;
    }
    if (isSorting) {
        return true;
    }
    return newIndex !== index && containerId === previousContainerId;
};
const defaultTransition = {
    duration: 200,
    easing: 'ease'
};
const transitionProperty = 'transform';
const disabledTransition = /*#__PURE__*/ __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CSS"].Transition.toString({
    property: transitionProperty,
    duration: 0,
    easing: 'linear'
});
const defaultAttributes = {
    roleDescription: 'sortable'
};
/*
 * When the index of an item changes while sorting,
 * we need to temporarily disable the transforms
 */ function useDerivedTransform(_ref) {
    let { disabled, index, node, rect } = _ref;
    const [derivedTransform, setDerivedtransform] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const previousIndex = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(index);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useIsomorphicLayoutEffect"])({
        "useDerivedTransform.useIsomorphicLayoutEffect": ()=>{
            if (!disabled && index !== previousIndex.current && node.current) {
                const initial = rect.current;
                if (initial) {
                    const current = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getClientRect"])(node.current, {
                        ignoreTransform: true
                    });
                    const delta = {
                        x: initial.left - current.left,
                        y: initial.top - current.top,
                        scaleX: initial.width / current.width,
                        scaleY: initial.height / current.height
                    };
                    if (delta.x || delta.y) {
                        setDerivedtransform(delta);
                    }
                }
            }
            if (index !== previousIndex.current) {
                previousIndex.current = index;
            }
        }
    }["useDerivedTransform.useIsomorphicLayoutEffect"], [
        disabled,
        index,
        node,
        rect
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "useDerivedTransform.useEffect": ()=>{
            if (derivedTransform) {
                setDerivedtransform(null);
            }
        }
    }["useDerivedTransform.useEffect"], [
        derivedTransform
    ]);
    return derivedTransform;
}
function useSortable(_ref) {
    let { animateLayoutChanges = defaultAnimateLayoutChanges, attributes: userDefinedAttributes, disabled: localDisabled, data: customData, getNewIndex = defaultNewIndexGetter, id, strategy: localStrategy, resizeObserverConfig, transition = defaultTransition } = _ref;
    const { items, containerId, activeIndex, disabled: globalDisabled, disableTransforms, sortedRects, overIndex, useDragOverlay, strategy: globalStrategy } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useContext"])(Context);
    const disabled = normalizeLocalDisabled(localDisabled, globalDisabled);
    const index = items.indexOf(id);
    const data = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useSortable.useMemo[data]": ()=>({
                sortable: {
                    containerId,
                    index,
                    items
                },
                ...customData
            })
    }["useSortable.useMemo[data]"], [
        containerId,
        customData,
        index,
        items
    ]);
    const itemsAfterCurrentSortable = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "useSortable.useMemo[itemsAfterCurrentSortable]": ()=>items.slice(items.indexOf(id))
    }["useSortable.useMemo[itemsAfterCurrentSortable]"], [
        items,
        id
    ]);
    const { rect, node, isOver, setNodeRef: setDroppableNodeRef } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDroppable"])({
        id,
        data,
        disabled: disabled.droppable,
        resizeObserverConfig: {
            updateMeasurementsFor: itemsAfterCurrentSortable,
            ...resizeObserverConfig
        }
    });
    const { active, activatorEvent, activeNodeRect, attributes, setNodeRef: setDraggableNodeRef, listeners, isDragging, over, setActivatorNodeRef, transform } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDraggable"])({
        id,
        data,
        attributes: {
            ...defaultAttributes,
            ...userDefinedAttributes
        },
        disabled: disabled.draggable
    });
    const setNodeRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCombinedRefs"])(setDroppableNodeRef, setDraggableNodeRef);
    const isSorting = Boolean(active);
    const displaceItem = isSorting && !disableTransforms && isValidIndex(activeIndex) && isValidIndex(overIndex);
    const shouldDisplaceDragSource = !useDragOverlay && isDragging;
    const dragSourceDisplacement = shouldDisplaceDragSource && displaceItem ? transform : null;
    const strategy = localStrategy != null ? localStrategy : globalStrategy;
    const finalTransform = displaceItem ? dragSourceDisplacement != null ? dragSourceDisplacement : strategy({
        rects: sortedRects,
        activeNodeRect,
        activeIndex,
        overIndex,
        index
    }) : null;
    const newIndex = isValidIndex(activeIndex) && isValidIndex(overIndex) ? getNewIndex({
        id,
        items,
        activeIndex,
        overIndex
    }) : index;
    const activeId = active == null ? void 0 : active.id;
    const previous = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])({
        activeId,
        items,
        newIndex,
        containerId
    });
    const itemsHaveChanged = items !== previous.current.items;
    const shouldAnimateLayoutChanges = animateLayoutChanges({
        active,
        containerId,
        isDragging,
        isSorting,
        id,
        index,
        items,
        newIndex: previous.current.newIndex,
        previousItems: previous.current.items,
        previousContainerId: previous.current.containerId,
        transition,
        wasDragging: previous.current.activeId != null
    });
    const derivedTransform = useDerivedTransform({
        disabled: !shouldAnimateLayoutChanges,
        index,
        node,
        rect
    });
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "useSortable.useEffect": ()=>{
            if (isSorting && previous.current.newIndex !== newIndex) {
                previous.current.newIndex = newIndex;
            }
            if (containerId !== previous.current.containerId) {
                previous.current.containerId = containerId;
            }
            if (items !== previous.current.items) {
                previous.current.items = items;
            }
        }
    }["useSortable.useEffect"], [
        isSorting,
        newIndex,
        containerId,
        items
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "useSortable.useEffect": ()=>{
            if (activeId === previous.current.activeId) {
                return;
            }
            if (activeId != null && previous.current.activeId == null) {
                previous.current.activeId = activeId;
                return;
            }
            const timeoutId = setTimeout({
                "useSortable.useEffect.timeoutId": ()=>{
                    previous.current.activeId = activeId;
                }
            }["useSortable.useEffect.timeoutId"], 50);
            return ({
                "useSortable.useEffect": ()=>clearTimeout(timeoutId)
            })["useSortable.useEffect"];
        }
    }["useSortable.useEffect"], [
        activeId
    ]);
    return {
        active,
        activeIndex,
        attributes,
        data,
        rect,
        index,
        newIndex,
        items,
        isOver,
        isSorting,
        isDragging,
        listeners,
        node,
        overIndex,
        over,
        setNodeRef,
        setActivatorNodeRef,
        setDroppableNodeRef,
        setDraggableNodeRef,
        transform: derivedTransform != null ? derivedTransform : finalTransform,
        transition: getTransition()
    };
    //TURBOPACK unreachable
    ;
    function getTransition() {
        if (derivedTransform || // Or to prevent items jumping to back to their "new" position when items change
        itemsHaveChanged && previous.current.newIndex === index) {
            return disabledTransition;
        }
        if (shouldDisplaceDragSource && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["isKeyboardEvent"])(activatorEvent) || !transition) {
            return undefined;
        }
        if (isSorting || shouldAnimateLayoutChanges) {
            return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["CSS"].Transition.toString({
                ...transition,
                property: transitionProperty
            });
        }
        return undefined;
    }
}
function normalizeLocalDisabled(localDisabled, globalDisabled) {
    var _localDisabled$dragga, _localDisabled$droppa;
    if (typeof localDisabled === 'boolean') {
        return {
            draggable: localDisabled,
            // Backwards compatibility
            droppable: false
        };
    }
    return {
        draggable: (_localDisabled$dragga = localDisabled == null ? void 0 : localDisabled.draggable) != null ? _localDisabled$dragga : globalDisabled.draggable,
        droppable: (_localDisabled$droppa = localDisabled == null ? void 0 : localDisabled.droppable) != null ? _localDisabled$droppa : globalDisabled.droppable
    };
}
function hasSortableData(entry) {
    if (!entry) {
        return false;
    }
    const data = entry.data.current;
    if (data && 'sortable' in data && typeof data.sortable === 'object' && 'containerId' in data.sortable && 'items' in data.sortable && 'index' in data.sortable) {
        return true;
    }
    return false;
}
const directions = [
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Down,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Right,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Up,
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Left
];
const sortableKeyboardCoordinates = (event, _ref)=>{
    let { context: { active, collisionRect, droppableRects, droppableContainers, over, scrollableAncestors } } = _ref;
    if (directions.includes(event.code)) {
        event.preventDefault();
        if (!active || !collisionRect) {
            return;
        }
        const filteredContainers = [];
        droppableContainers.getEnabled().forEach((entry)=>{
            if (!entry || entry != null && entry.disabled) {
                return;
            }
            const rect = droppableRects.get(entry.id);
            if (!rect) {
                return;
            }
            switch(event.code){
                case __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Down:
                    if (collisionRect.top < rect.top) {
                        filteredContainers.push(entry);
                    }
                    break;
                case __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Up:
                    if (collisionRect.top > rect.top) {
                        filteredContainers.push(entry);
                    }
                    break;
                case __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Left:
                    if (collisionRect.left > rect.left) {
                        filteredContainers.push(entry);
                    }
                    break;
                case __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Right:
                    if (collisionRect.left < rect.left) {
                        filteredContainers.push(entry);
                    }
                    break;
            }
        });
        const collisions = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["closestCorners"])({
            active,
            collisionRect: collisionRect,
            droppableRects,
            droppableContainers: filteredContainers,
            pointerCoordinates: null
        });
        let closestId = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getFirstCollision"])(collisions, 'id');
        if (closestId === (over == null ? void 0 : over.id) && collisions.length > 1) {
            closestId = collisions[1].id;
        }
        if (closestId != null) {
            const activeDroppable = droppableContainers.get(active.id);
            const newDroppable = droppableContainers.get(closestId);
            const newRect = newDroppable ? droppableRects.get(newDroppable.id) : null;
            const newNode = newDroppable == null ? void 0 : newDroppable.node.current;
            if (newNode && newRect && activeDroppable && newDroppable) {
                const newScrollAncestors = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getScrollableAncestors"])(newNode);
                const hasDifferentScrollAncestors = newScrollAncestors.some((element, index)=>scrollableAncestors[index] !== element);
                const hasSameContainer = isSameContainer(activeDroppable, newDroppable);
                const isAfterActive = isAfter(activeDroppable, newDroppable);
                const offset = hasDifferentScrollAncestors || !hasSameContainer ? {
                    x: 0,
                    y: 0
                } : {
                    x: isAfterActive ? collisionRect.width - newRect.width : 0,
                    y: isAfterActive ? collisionRect.height - newRect.height : 0
                };
                const rectCoordinates = {
                    x: newRect.left,
                    y: newRect.top
                };
                const newCoordinates = offset.x && offset.y ? rectCoordinates : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$utilities$2f$dist$2f$utilities$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["subtract"])(rectCoordinates, offset);
                return newCoordinates;
            }
        }
    }
    return undefined;
};
function isSameContainer(a, b) {
    if (!hasSortableData(a) || !hasSortableData(b)) {
        return false;
    }
    return a.data.current.sortable.containerId === b.data.current.sortable.containerId;
}
function isAfter(a, b) {
    if (!hasSortableData(a) || !hasSortableData(b)) {
        return false;
    }
    if (!isSameContainer(a, b)) {
        return false;
    }
    return a.data.current.sortable.index < b.data.current.sortable.index;
}
;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/FormHeader/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "FormHeader",
    ()=>FormHeader
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
;
;
const baseClass = 'form-header';
function FormHeader({ description, heading }) {
    if (!heading) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
        className: baseClass,
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("h1", {
                children: heading
            }),
            Boolean(description) && /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("p", {
                children: description
            })
        ]
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/ResetPreferences/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ResetPreferences",
    ()=>ResetPreferences
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$stringify$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/qs-esm/lib/stringify.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const confirmResetModalSlug = 'confirm-reset-modal';
const ResetPreferences = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(9);
    const { user } = t0;
    const { openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { routes: t2 } = t1;
    const { api: apiRoute } = t2;
    let t3;
    if ($[0] !== apiRoute || $[1] !== user) {
        t3 = async ()=>{
            if (!user) {
                return;
            }
            const stringifiedQuery = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$qs$2d$esm$2f$lib$2f$stringify$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["stringify"]({
                depth: 0,
                where: {
                    "user.value": {
                        equals: user.id
                    }
                }
            }, {
                addQueryPrefix: true
            });
            ;
            try {
                const res = await fetch((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                    apiRoute,
                    path: `/payload-preferences${stringifiedQuery}`
                }), {
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    method: "DELETE"
                });
                const json = await res.json();
                const message = json.message;
                if (res.ok) {
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].success(message);
                } else {
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(message);
                }
            } catch (t4) {
                const _err = t4;
            }
        };
        $[0] = apiRoute;
        $[1] = user;
        $[2] = t3;
    } else {
        t3 = $[2];
    }
    const handleResetPreferences = t3;
    let t4;
    if ($[3] !== openModal) {
        t4 = ()=>openModal(confirmResetModalSlug);
        $[3] = openModal;
        $[4] = t4;
    } else {
        t4 = $[4];
    }
    let t5;
    if ($[5] !== handleResetPreferences || $[6] !== t || $[7] !== t4) {
        t5 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                        buttonStyle: "secondary",
                        onClick: t4,
                        children: t("general:resetPreferences")
                    })
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmationModal"], {
                    body: t("general:resetPreferencesDescription"),
                    confirmingLabel: t("general:resettingPreferences"),
                    heading: t("general:resetPreferences"),
                    modalSlug: confirmResetModalSlug,
                    onConfirm: handleResetPreferences
                })
            ]
        });
        $[5] = handleResetPreferences;
        $[6] = t;
        $[7] = t4;
        $[8] = t5;
    } else {
        t5 = $[8];
    }
    return t5;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/Settings/LanguageSelector.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LanguageSelector",
    ()=>LanguageSelector
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const LanguageSelector = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(8);
    const { languageOptions } = props;
    const { i18n, switchLanguage } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t0;
    if ($[0] !== switchLanguage) {
        t0 = async (option)=>{
            await switchLanguage(option.value);
        };
        $[0] = switchLanguage;
        $[1] = t0;
    } else {
        t0 = $[1];
    }
    let t1;
    if ($[2] !== i18n || $[3] !== languageOptions || $[4] !== t0) {
        let t2;
        if ($[6] !== i18n) {
            t2 = (language)=>language.value === i18n.language;
            $[6] = i18n;
            $[7] = t2;
        } else {
            t2 = $[7];
        }
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ReactSelect"], {
            inputId: "language-select",
            isClearable: false,
            onChange: t0,
            options: languageOptions,
            value: languageOptions.find(t2)
        });
        $[2] = i18n;
        $[3] = languageOptions;
        $[4] = t0;
        $[5] = t1;
    } else {
        t1 = $[5];
    }
    return t1;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/ToggleTheme/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ToggleTheme",
    ()=>ToggleTheme
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__j__as__useTheme$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export j as useTheme>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const ToggleTheme = ()=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(7);
    const { autoMode, setTheme, theme } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__j__as__useTheme$3e$__["useTheme"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t0;
    if ($[0] !== setTheme) {
        t0 = (newTheme)=>{
            setTheme(newTheme);
        };
        $[0] = setTheme;
        $[1] = t0;
    } else {
        t0 = $[1];
    }
    const onChange = t0;
    let t1;
    if ($[2] !== autoMode || $[3] !== onChange || $[4] !== t || $[5] !== theme) {
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["RadioGroupField"], {
            disableModifyingForm: true,
            field: {
                name: "theme",
                label: t("general:adminTheme"),
                options: [
                    {
                        label: t("general:automatic"),
                        value: "auto"
                    },
                    {
                        label: t("general:light"),
                        value: "light"
                    },
                    {
                        label: t("general:dark"),
                        value: "dark"
                    }
                ]
            },
            onChange,
            path: "theme",
            value: autoMode ? "auto" : theme
        });
        $[2] = autoMode;
        $[3] = onChange;
        $[4] = t;
        $[5] = theme;
        $[6] = t1;
    } else {
        t1 = $[6];
    }
    return t1;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Account/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "AccountClient",
    ()=>AccountClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const AccountClient = ()=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(4);
    const { setStepNav } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useStepNav"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    let t0;
    let t1;
    if ($[0] !== setStepNav || $[1] !== t) {
        t0 = ()=>{
            const nav = [];
            nav.push({
                label: t("authentication:account"),
                url: "/account"
            });
            setStepNav(nav);
        };
        t1 = [
            setStepNav,
            t
        ];
        $[0] = setStepNav;
        $[1] = t;
        $[2] = t0;
        $[3] = t1;
    } else {
        t0 = $[2];
        t1 = $[3];
    }
    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useEffect(t0, t1);
    return null;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/CreateFirstUser/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "CreateFirstUserClient",
    ()=>CreateFirstUserClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
const CreateFirstUserClient = ({ docPermissions, docPreferences, initialState, loginWithUsername, userSlug })=>{
    const { config: { routes: { admin, api: apiRoute } }, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { getFormState } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useServerFunctions"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { setUser } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAuth"])();
    const abortOnChangeRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useRef(null);
    const collectionConfig = getEntityConfig({
        collectionSlug: userSlug
    });
    const onChange = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useCallback({
        "CreateFirstUserClient.useCallback[onChange]": async ({ formState: prevFormState, submitted })=>{
            const controller = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["handleAbortRef"])(abortOnChangeRef);
            const response = await getFormState({
                collectionSlug: userSlug,
                docPermissions,
                docPreferences,
                formState: prevFormState,
                operation: 'create',
                schemaPath: userSlug,
                signal: controller.signal,
                skipValidation: !submitted
            });
            abortOnChangeRef.current = null;
            if (response && response.state) {
                return response.state;
            }
        }
    }["CreateFirstUserClient.useCallback[onChange]"], [
        userSlug,
        getFormState,
        docPermissions,
        docPreferences
    ]);
    const handleFirstRegister = (data)=>{
        setUser(data);
    };
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "CreateFirstUserClient.useEffect": ()=>{
            const abortOnChange = abortOnChangeRef.current;
            return ({
                "CreateFirstUserClient.useEffect": ()=>{
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["abortAndIgnore"])(abortOnChange);
                }
            })["CreateFirstUserClient.useEffect"];
        }
    }["CreateFirstUserClient.useEffect"], []);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
        action: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
            apiRoute,
            path: `/${userSlug}/first-register`
        }),
        initialState: {
            ...initialState,
            'confirm-password': {
                ...initialState['confirm-password'],
                valid: initialState['confirm-password']['valid'] || false,
                value: initialState['confirm-password']['value'] || ''
            }
        },
        method: "POST",
        onChange: [
            onChange
        ],
        onSuccess: handleFirstRegister,
        redirect: admin,
        validationOperation: "create",
        children: [
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EmailAndUsernameFields"], {
                className: "emailAndUsername",
                loginWithUsername: loginWithUsername,
                operation: "create",
                readOnly: false,
                t: t
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PasswordField"], {
                autoComplete: "off",
                field: {
                    name: 'password',
                    label: t('authentication:newPassword'),
                    required: true
                },
                path: "password"
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmPasswordField"], {}),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["RenderFields"], {
                fields: collectionConfig.fields,
                forceRender: true,
                parentIndexPath: "",
                parentPath: "",
                parentSchemaPath: userSlug,
                permissions: true,
                readOnly: false
            }),
            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FormSubmit"], {
                size: "large",
                children: t('general:create')
            })
        ]
    });
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/DashboardStepNav.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "DashboardBreadcrumbDropdown",
    ()=>DashboardBreadcrumbDropdown,
    "DashboardStepNav",
    ()=>DashboardStepNav
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
function DashboardStepNav(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(15);
    const { addWidget, cancel, isEditing, resetLayout, saveLayout, setIsEditing, widgets } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { setStepNav } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useStepNav"])();
    const uuid = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])();
    const drawerSlug = `widgets-drawer-${uuid}`;
    let t1;
    let t2;
    if ($[0] !== cancel || $[1] !== drawerSlug || $[2] !== isEditing || $[3] !== resetLayout || $[4] !== saveLayout || $[5] !== setIsEditing || $[6] !== setStepNav) {
        t1 = ()=>{
            setStepNav([
                {
                    label: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DashboardBreadcrumbDropdown, {
                        isEditing,
                        onCancel: cancel,
                        onEditClick: ()=>setIsEditing(true),
                        onResetLayout: resetLayout,
                        onSaveChanges: saveLayout,
                        widgetsDrawerSlug: drawerSlug
                    })
                }
            ]);
        };
        t2 = [
            isEditing,
            drawerSlug,
            cancel,
            resetLayout,
            saveLayout,
            setIsEditing,
            setStepNav
        ];
        $[0] = cancel;
        $[1] = drawerSlug;
        $[2] = isEditing;
        $[3] = resetLayout;
        $[4] = saveLayout;
        $[5] = setIsEditing;
        $[6] = setStepNav;
        $[7] = t1;
        $[8] = t2;
    } else {
        t1 = $[7];
        t2 = $[8];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t1, t2);
    let t3;
    if ($[9] !== addWidget || $[10] !== drawerSlug || $[11] !== isEditing || $[12] !== t || $[13] !== widgets) {
        t3 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: isEditing && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ItemsDrawer"], {
                drawerSlug,
                items: widgets,
                onItemClick: (widget)=>addWidget(widget.slug),
                searchPlaceholder: t("dashboard:searchWidgets"),
                title: t("dashboard:addWidget")
            })
        });
        $[9] = addWidget;
        $[10] = drawerSlug;
        $[11] = isEditing;
        $[12] = t;
        $[13] = widgets;
        $[14] = t3;
    } else {
        t3 = $[14];
    }
    return t3;
}
function DashboardBreadcrumbDropdown(props) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(12);
    const { isEditing, onCancel, onEditClick, onResetLayout, onSaveChanges, widgetsDrawerSlug } = props;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    if (isEditing) {
        let t0;
        if ($[0] !== onCancel || $[1] !== onSaveChanges || $[2] !== t || $[3] !== widgetsDrawerSlug) {
            t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: "dashboard-breadcrumb-dropdown__editing",
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                        children: t("dashboard:editingDashboard")
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: "dashboard-breadcrumb-dropdown__actions",
                        children: [
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["DrawerToggler"], {
                                className: "drawer-toggler--unstyled",
                                slug: widgetsDrawerSlug,
                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                                    buttonStyle: "pill",
                                    el: "span",
                                    size: "small",
                                    children: t("dashboard:addButton")
                                })
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                                buttonStyle: "pill",
                                onClick: onSaveChanges,
                                size: "small",
                                children: t("fields:saveChanges")
                            }),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                                buttonStyle: "pill",
                                onClick: onCancel,
                                size: "small",
                                children: t("general:cancel")
                            })
                        ]
                    })
                ]
            });
            $[0] = onCancel;
            $[1] = onSaveChanges;
            $[2] = t;
            $[3] = widgetsDrawerSlug;
            $[4] = t0;
        } else {
            t0 = $[4];
        }
        return t0;
    }
    let t0;
    if ($[5] !== onEditClick || $[6] !== onResetLayout || $[7] !== t) {
        const options = [
            {
                label: t("dashboard:editDashboard"),
                value: "edit"
            },
            {
                label: t("dashboard:resetLayout"),
                value: "reset"
            }
        ];
        let t1;
        if ($[9] !== onEditClick || $[10] !== onResetLayout) {
            t1 = (selectedOption)=>{
                const option = Array.isArray(selectedOption) ? selectedOption[0] : selectedOption;
                if (option?.value === "edit") {
                    onEditClick();
                } else {
                    if (option?.value === "reset") {
                        onResetLayout();
                    }
                }
            };
            $[9] = onEditClick;
            $[10] = onResetLayout;
            $[11] = t1;
        } else {
            t1 = $[11];
        }
        const handleChange = t1;
        t0 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ReactSelect"], {
            className: "dashboard-breadcrumb-select",
            isClearable: false,
            isSearchable: false,
            menuIsOpen: undefined,
            onChange: handleChange,
            options,
            placeholder: t("general:dashboard"),
            value: {
                label: t("general:dashboard"),
                value: "dashboard"
            }
        });
        $[5] = onEditClick;
        $[6] = onResetLayout;
        $[7] = t;
        $[8] = t0;
    } else {
        t0 = $[8];
    }
    return t0;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/WidgetConfigDrawer.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "WidgetConfigDrawer",
    ()=>WidgetConfigDrawer
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export f as ShimmerEffect>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/shared/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$v4$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__v4$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/v4.js [app-client] (ecmascript) <export default as v4>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$localeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/localeUtils.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const EMPTY_WIDGET_PREFERENCES = {
    fields: {}
};
function WidgetConfigDrawer({ drawerSlug, onSave, widget, widgetData }) {
    const { closeModal, modalState } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const { getFormState } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useServerFunctions"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const locale = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useLocale"])();
    const localeCode = locale?.code ?? 'en';
    const onChangeAbortControllerRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(null);
    const [initialState, setInitialState] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const isOpen = Boolean(modalState?.[drawerSlug]?.isOpen);
    const formUUID = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "WidgetConfigDrawer.useMemo[formUUID]": ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$v4$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__default__as__v4$3e$__["v4"])()
    }["WidgetConfigDrawer.useMemo[formUUID]"], []);
    const widgetLabel = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "WidgetConfigDrawer.useMemo[widgetLabel]": ()=>typeof widget.label === 'string' ? widget.label : widget.slug
    }["WidgetConfigDrawer.useMemo[widgetLabel]"], [
        widget.label,
        widget.slug
    ]);
    const fields = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "WidgetConfigDrawer.useMemo[fields]": ()=>widget.fields ?? []
    }["WidgetConfigDrawer.useMemo[fields]"], [
        widget.fields
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "WidgetConfigDrawer.useEffect": ()=>{
            if (!isOpen || fields.length === 0) {
                setInitialState(false);
                return;
            }
            const controller = new AbortController();
            const loadInitialState = {
                "WidgetConfigDrawer.useEffect.loadInitialState": async ()=>{
                    const localeFilteredData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$localeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["extractLocaleData"])(widgetData ?? {}, localeCode, fields);
                    const { state } = await getFormState({
                        data: localeFilteredData,
                        docPermissions: {
                            fields: true
                        },
                        docPreferences: EMPTY_WIDGET_PREFERENCES,
                        locale: localeCode,
                        operation: 'update',
                        renderAllFields: true,
                        schemaPath: widget.slug,
                        signal: controller.signal,
                        widgetSlug: widget.slug
                    });
                    if (state) {
                        setInitialState(state);
                    }
                }
            }["WidgetConfigDrawer.useEffect.loadInitialState"];
            void loadInitialState();
            return ({
                "WidgetConfigDrawer.useEffect": ()=>{
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["abortAndIgnore"])(controller);
                }
            })["WidgetConfigDrawer.useEffect"];
        }
    }["WidgetConfigDrawer.useEffect"], [
        fields,
        getFormState,
        isOpen,
        localeCode,
        widget.slug,
        widgetData
    ]);
    const onChange = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "WidgetConfigDrawer.useCallback[onChange]": async ({ formState: prevFormState })=>{
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["abortAndIgnore"])(onChangeAbortControllerRef.current);
            const controller_0 = new AbortController();
            onChangeAbortControllerRef.current = controller_0;
            const { state: state_0 } = await getFormState({
                docPermissions: {
                    fields: true
                },
                docPreferences: EMPTY_WIDGET_PREFERENCES,
                formState: prevFormState,
                operation: 'update',
                schemaPath: widget.slug,
                signal: controller_0.signal,
                widgetSlug: widget.slug
            });
            if (!state_0) {
                return prevFormState;
            }
            return state_0;
        }
    }["WidgetConfigDrawer.useCallback[onChange]"], [
        getFormState,
        widget.slug
    ]);
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "WidgetConfigDrawer.useEffect": ()=>{
            return ({
                "WidgetConfigDrawer.useEffect": ()=>{
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$shared$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["abortAndIgnore"])(onChangeAbortControllerRef.current);
                }
            })["WidgetConfigDrawer.useEffect"];
        }
    }["WidgetConfigDrawer.useEffect"], []);
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Drawer"], {
        slug: drawerSlug,
        title: `${t('general:edit')} ${widgetLabel}`,
        children: initialState === false ? /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__["ShimmerEffect"], {
            height: "250px"
        }) : /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["OperationProvider"], {
            operation: "update",
            children: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
                fields: fields,
                initialState: initialState,
                onChange: [
                    onChange
                ],
                onSubmit: (_, data)=>{
                    onSave((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$localeUtils$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["mergeLocaleData"])(widgetData ?? {}, data, localeCode, fields));
                    closeModal(drawerSlug);
                },
                uuid: formUUID,
                children: [
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["RenderFields"], {
                        fields: fields,
                        forceRender: true,
                        parentIndexPath: "",
                        parentPath: "",
                        parentSchemaPath: widget.slug,
                        permissions: true,
                        readOnly: false
                    }),
                    /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FormSubmit"], {
                        children: t('fields:saveChanges')
                    })
                ]
            })
        })
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/WidgetEditControl.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "WidgetEditControl",
    ()=>WidgetEditControl
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$WidgetConfigDrawer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/WidgetConfigDrawer.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
const getWidgetSlugFromID = (widgetID)=>widgetID.slice(0, widgetID.lastIndexOf('-'));
function WidgetEditControl(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(7);
    const { onSave, widgetData, widgetID } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const { widgets: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])().config.admin.dashboard ?? {};
    const configWidgets = t1 === undefined ? [] : t1;
    let t2;
    if ($[0] !== widgetID) {
        t2 = getWidgetSlugFromID(widgetID);
        $[0] = widgetID;
        $[1] = t2;
    } else {
        t2 = $[1];
    }
    const widgetSlug = t2;
    let t3;
    if ($[2] !== widgetSlug) {
        t3 = (widget)=>widget.slug === widgetSlug;
        $[2] = widgetSlug;
        $[3] = t3;
    } else {
        t3 = $[3];
    }
    const widgetConfig = configWidgets.find(t3);
    const hasEditableFields = Boolean(widgetConfig?.fields?.length);
    const drawerID = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useId"])();
    const drawerSlug = `widget-editor-${drawerID}`;
    if (!hasEditableFields) {
        return null;
    }
    let t4;
    if ($[4] !== drawerSlug || $[5] !== openModal) {
        t4 = ()=>{
            openModal(drawerSlug);
        };
        $[4] = drawerSlug;
        $[5] = openModal;
        $[6] = t4;
    } else {
        t4 = $[6];
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
        children: [
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("button", {
                className: "widget-wrapper__edit-btn",
                onClick: t4,
                type: "button",
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                        className: "sr-only",
                        children: [
                            t("general:edit"),
                            " ",
                            widgetID
                        ]
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EditIcon"], {})
                ]
            }),
            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$WidgetConfigDrawer$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["WidgetConfigDrawer"], {
                drawerSlug,
                onSave,
                widget: widgetConfig,
                widgetData
            })
        ]
    });
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ModularDashboardClient",
    ()=>ModularDashboardClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/core/dist/core.esm.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$modifiers$2f$dist$2f$modifiers$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/modifiers/dist/modifiers.esm.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__a__as__XIcon$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export a as XIcon>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$DashboardStepNav$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/DashboardStepNav.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$useDashboardLayout$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/useDashboardLayout.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$collisionDetection$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/collisionDetection.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$sensors$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/sensors.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$WidgetEditControl$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/WidgetEditControl.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
/**
 * Custom modifier that only applies snapCenterToCursor for pointer events.
 * During keyboard navigation, we handle positioning ourselves via the coordinate getter.
 */ const snapCenterToCursorOnlyForPointer = (args)=>{
    const { activatorEvent } = args;
    // Only apply snap for pointer events (mouse/touch), not keyboard
    // Check activatorEvent.type since KeyboardEvent may not exist on server
    if (activatorEvent && 'key' in activatorEvent) {
        return args.transform;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$modifiers$2f$dist$2f$modifiers$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["snapCenterToCursor"])(args);
};
;
;
;
;
;
/* eslint-disable perfectionist/sort-objects */ const WIDTH_TO_PERCENTAGE = {
    'x-small': 25,
    small: 1 / 3 * 100,
    medium: 50,
    large: 2 / 3 * 100,
    'x-large': 75,
    full: 100
};
function ModularDashboardClient(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(22);
    const { clientLayout: initialLayout, widgets } = t0;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { addWidget, cancel, cancelModal, currentLayout, deleteWidget, isEditing, moveWidget, resetLayout, resizeWidget, saveLayout, setIsEditing, updateWidgetData } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$useDashboardLayout$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDashboardLayout"])(initialLayout);
    const [activeDragId, setActiveDragId] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(null);
    const sensors = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$sensors$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDashboardSensors"])();
    let t1;
    if ($[0] !== activeDragId || $[1] !== addWidget || $[2] !== cancel || $[3] !== cancelModal || $[4] !== currentLayout || $[5] !== deleteWidget || $[6] !== isEditing || $[7] !== moveWidget || $[8] !== resetLayout || $[9] !== resizeWidget || $[10] !== saveLayout || $[11] !== sensors || $[12] !== setIsEditing || $[13] !== t || $[14] !== updateWidgetData || $[15] !== widgets) {
        let t2;
        if ($[17] === Symbol.for("react.memo_cache_sentinel")) {
            t2 = ()=>{
                setActiveDragId(null);
            };
            $[17] = t2;
        } else {
            t2 = $[17];
        }
        let t3;
        if ($[18] !== currentLayout || $[19] !== moveWidget) {
            t3 = (event)=>{
                if (!event.over) {
                    setActiveDragId(null);
                    return;
                }
                const droppableId = event.over.id;
                const i = droppableId.lastIndexOf("-");
                const slug = droppableId.slice(0, i);
                const position = droppableId.slice(i + 1);
                if (slug === event.active.id) {
                    return;
                }
                const moveFromIndex = currentLayout?.findIndex((widget)=>widget.item.id === event.active.id);
                let moveToIndex = currentLayout?.findIndex((widget_0)=>widget_0.item.id === slug);
                if (moveFromIndex < moveToIndex) {
                    moveToIndex--;
                }
                if (position === "after") {
                    moveToIndex++;
                }
                moveWidget({
                    moveFromIndex,
                    moveToIndex
                });
                setActiveDragId(null);
            };
            $[18] = currentLayout;
            $[19] = moveWidget;
            $[20] = t3;
        } else {
            t3 = $[20];
        }
        let t4;
        if ($[21] === Symbol.for("react.memo_cache_sentinel")) {
            t4 = (event_0)=>{
                setActiveDragId(event_0.active.id);
            };
            $[21] = t4;
        } else {
            t4 = $[21];
        }
        t1 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DndContext"], {
                    autoScroll: {
                        enabled: true,
                        threshold: {
                            x: 0,
                            y: 0.2
                        }
                    },
                    collisionDetection: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$utils$2f$collisionDetection$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["closestInXAxis"],
                    id: "dashboard-dnd-context",
                    onDragCancel: t2,
                    onDragEnd: t3,
                    onDragStart: t4,
                    sensors,
                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                        className: `modular-dashboard ${isEditing ? "editing" : ""}`,
                        style: {
                            display: "flex",
                            flexWrap: "wrap"
                        },
                        children: [
                            currentLayout?.length === 0 && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                className: "modular-dashboard__empty",
                                children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("p", {
                                    children: t("dashboard:noItems")
                                })
                            }),
                            currentLayout?.map((widget_1, _index)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].Fragment, {
                                    children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DraggableItem, {
                                        disabled: !isEditing,
                                        id: widget_1.item.id,
                                        style: {
                                            width: `${WIDTH_TO_PERCENTAGE[widget_1.item.width]}%`,
                                            padding: "6px"
                                        },
                                        width: widget_1.item.width,
                                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                            className: `widget-wrapper ${isEditing ? "widget-wrapper--editing" : ""}`,
                                            children: [
                                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                                    "aria-hidden": isEditing,
                                                    className: "widget-content",
                                                    inert: isEditing,
                                                    children: widget_1.component
                                                }),
                                                isEditing && (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                                                    className: "widget-wrapper__controls",
                                                    onPointerDown: _temp,
                                                    children: [
                                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$WidgetEditControl$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["WidgetEditControl"], {
                                                            onSave: (data)=>{
                                                                updateWidgetData(widget_1.item.id, data);
                                                            },
                                                            widgetData: widget_1.item.data,
                                                            widgetID: widget_1.item.id
                                                        }),
                                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(WidgetWidthDropdown, {
                                                            currentWidth: widget_1.item.width,
                                                            maxWidth: widget_1.item.maxWidth,
                                                            minWidth: widget_1.item.minWidth,
                                                            onResize: (width)=>resizeWidget(widget_1.item.id, width)
                                                        }),
                                                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("button", {
                                                            className: "widget-wrapper__delete-btn",
                                                            onClick: ()=>deleteWidget(widget_1.item.id),
                                                            type: "button",
                                                            children: [
                                                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                                                    className: "sr-only",
                                                                    children: t("dashboard:deleteWidget", {
                                                                        id: widget_1.item.id
                                                                    })
                                                                }),
                                                                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__a__as__XIcon$3e$__["XIcon"], {})
                                                            ]
                                                        })
                                                    ]
                                                })
                                            ]
                                        })
                                    })
                                }, widget_1.item.id)),
                            (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DragOverlay"], {
                                className: "drag-overlay",
                                dropAnimation: {
                                    duration: 100
                                },
                                modifiers: [
                                    snapCenterToCursorOnlyForPointer
                                ],
                                children: activeDragId ? (()=>{
                                    const draggedWidget = currentLayout?.find((widget_2)=>widget_2.item.id === activeDragId);
                                    return draggedWidget ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                        style: {
                                            transform: "scale(0.25)"
                                        },
                                        children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                            className: `widget-wrapper ${isEditing ? "widget-wrapper--editing" : ""}`,
                                            children: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                                                className: "widget-content",
                                                children: draggedWidget.component
                                            })
                                        })
                                    }) : null;
                                })() : null
                            })
                        ]
                    })
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$DashboardStepNav$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["DashboardStepNav"], {
                    addWidget,
                    cancel,
                    isEditing,
                    resetLayout,
                    saveLayout,
                    setIsEditing,
                    widgets
                }),
                cancelModal
            ]
        });
        $[0] = activeDragId;
        $[1] = addWidget;
        $[2] = cancel;
        $[3] = cancelModal;
        $[4] = currentLayout;
        $[5] = deleteWidget;
        $[6] = isEditing;
        $[7] = moveWidget;
        $[8] = resetLayout;
        $[9] = resizeWidget;
        $[10] = saveLayout;
        $[11] = sensors;
        $[12] = setIsEditing;
        $[13] = t;
        $[14] = updateWidgetData;
        $[15] = widgets;
        $[16] = t1;
    } else {
        t1 = $[16];
    }
    return t1;
}
function _temp(e) {
    return e.stopPropagation();
}
function WidgetWidthDropdown({ currentWidth, maxWidth, minWidth, onResize }) {
    // Filter options based on minWidth and maxWidth
    const validOptions = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useMemo"])({
        "WidgetWidthDropdown.useMemo[validOptions]": ()=>{
            const minPercentage = WIDTH_TO_PERCENTAGE[minWidth];
            const maxPercentage = WIDTH_TO_PERCENTAGE[maxWidth];
            return Object.entries(WIDTH_TO_PERCENTAGE).map({
                "WidgetWidthDropdown.useMemo[validOptions]": ([key, value])=>({
                        width: key,
                        percentage: value
                    })
            }["WidgetWidthDropdown.useMemo[validOptions]"]).filter({
                "WidgetWidthDropdown.useMemo[validOptions]": (option)=>option.percentage >= minPercentage && option.percentage <= maxPercentage
            }["WidgetWidthDropdown.useMemo[validOptions]"]);
        }
    }["WidgetWidthDropdown.useMemo[validOptions]"], [
        minWidth,
        maxWidth
    ]);
    const isDisabled = validOptions.length <= 1;
    if (isDisabled) {
        return null;
    }
    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Popup"], {
        button: /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("button", {
            className: "widget-wrapper__size-btn",
            onPointerDown: (e)=>e.stopPropagation(),
            type: "button",
            children: [
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                    className: "widget-wrapper__size-btn-text",
                    children: currentWidth
                }),
                /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ChevronIcon"], {
                    className: "widget-wrapper__size-btn-icon"
                })
            ]
        }),
        buttonType: "custom",
        render: ({ close })=>/*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PopupList"].ButtonGroup, {
                children: validOptions.map((option_0)=>{
                    const isSelected = option_0.width === currentWidth;
                    return /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PopupList"].Button, {
                        active: isSelected,
                        onClick: ()=>{
                            onResize(option_0.width);
                            close();
                        },
                        children: [
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("span", {
                                className: "widget-wrapper__size-btn-label",
                                children: option_0.width
                            }),
                            /*#__PURE__*/ (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("span", {
                                className: "widget-wrapper__size-btn-percentage",
                                children: [
                                    option_0.percentage.toFixed(0),
                                    "%"
                                ]
                            })
                        ]
                    }, option_0.width);
                })
            }),
        size: "small",
        verticalAlign: "bottom"
    });
}
function DraggableItem(props) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(13);
    let t0;
    if ($[0] !== props.disabled || $[1] !== props.id) {
        t0 = {
            id: props.id,
            disabled: props.disabled
        };
        $[0] = props.disabled;
        $[1] = props.id;
        $[2] = t0;
    } else {
        t0 = $[2];
    }
    const { attributes, isDragging, listeners, setNodeRef } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDraggable"])(t0);
    const t1 = isDragging ? 0.3 : 1;
    let t2;
    if ($[3] !== attributes || $[4] !== listeners || $[5] !== props.children || $[6] !== props.disabled || $[7] !== props.id || $[8] !== props.style || $[9] !== props.width || $[10] !== setNodeRef || $[11] !== t1) {
        const mergedStyles = {
            ...props.style,
            opacity: t1,
            position: "relative"
        };
        const draggableProps = props.disabled ? {} : {
            ...listeners,
            ...attributes
        };
        t2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
            className: "widget",
            "data-slug": props.id,
            "data-width": props.width,
            style: mergedStyles,
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DroppableItem, {
                    id: props.id,
                    position: "before"
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
                    className: "draggable",
                    id: props.id,
                    ref: setNodeRef,
                    ...draggableProps,
                    style: {
                        width: "100%",
                        height: "100%"
                    },
                    children: props.children
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(DroppableItem, {
                    id: props.id,
                    position: "after"
                })
            ]
        });
        $[3] = attributes;
        $[4] = listeners;
        $[5] = props.children;
        $[6] = props.disabled;
        $[7] = props.id;
        $[8] = props.style;
        $[9] = props.width;
        $[10] = setNodeRef;
        $[11] = t1;
        $[12] = t2;
    } else {
        t2 = $[12];
    }
    return t2;
}
function DroppableItem(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    const { id, position } = t0;
    const t1 = `${id}-${position}`;
    let t2;
    if ($[0] !== position) {
        t2 = {
            position
        };
        $[0] = position;
        $[1] = t2;
    } else {
        t2 = $[1];
    }
    let t3;
    if ($[2] !== t1 || $[3] !== t2) {
        t3 = {
            id: t1,
            data: t2
        };
        $[2] = t1;
        $[3] = t2;
        $[4] = t3;
    } else {
        t3 = $[4];
    }
    const { setNodeRef, isOver } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useDroppable"])(t3);
    const t4 = `${id}-${position}`;
    const t5 = position === "before" ? -2 : "auto";
    const t6 = position === "after" ? -2 : "auto";
    const t7 = isOver ? "var(--theme-success-400)" : "transparent";
    let t8;
    if ($[5] !== setNodeRef || $[6] !== t4 || $[7] !== t5 || $[8] !== t6 || $[9] !== t7) {
        t8 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("div", {
            className: "droppable-widget",
            "data-testid": t4,
            ref: setNodeRef,
            style: {
                position: "absolute",
                left: t5,
                right: t6,
                top: 0,
                bottom: 0,
                borderRadius: "1000px",
                width: "4px",
                backgroundColor: t7,
                marginBottom: "10px",
                marginTop: "10px",
                pointerEvents: "none",
                zIndex: 1000
            }
        });
        $[5] = setNodeRef;
        $[6] = t4;
        $[7] = t5;
        $[8] = t6;
        $[9] = t7;
        $[10] = t8;
    } else {
        t8 = $[10];
    }
    return t8;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/renderWidget/RenderWidget.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "RenderWidget",
    ()=>RenderWidget
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export f as ShimmerEffect>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
const RenderWidget = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(10);
    const { widgetData, widgetId } = t0;
    const [Component, setComponent] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(null);
    const { serverFunction } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useServerFunctions"])();
    const requestIDRef = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRef"])(0);
    let t1;
    if ($[0] !== serverFunction || $[1] !== widgetData || $[2] !== widgetId) {
        t1 = ()=>{
            const render = async function render() {
                const requestID = requestIDRef.current = requestIDRef.current + 1;
                setComponent(null);
                ;
                try {
                    const widgetSlug = widgetId.slice(0, widgetId.lastIndexOf("-"));
                    const result = await serverFunction({
                        name: "render-widget",
                        args: {
                            widgetData,
                            widgetSlug
                        }
                    });
                    if (requestID !== requestIDRef.current) {
                        return;
                    }
                    setComponent(result.component);
                } catch (t2) {
                    if (requestID !== requestIDRef.current) {
                        return;
                    }
                    setComponent(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement("div", {
                        style: {
                            background: "var(--theme-error-50)",
                            border: "1px solid var(--theme-error-200)",
                            borderRadius: "4px",
                            color: "var(--theme-error-text)",
                            padding: "20px",
                            textAlign: "center"
                        }
                    }, "Failed to load widget. Please try again later."));
                }
            };
            render();
        };
        $[0] = serverFunction;
        $[1] = widgetData;
        $[2] = widgetId;
        $[3] = t1;
    } else {
        t1 = $[3];
    }
    const renderWidget = t1;
    let t2;
    let t3;
    if ($[4] !== renderWidget) {
        t2 = ()=>{
            renderWidget();
        };
        t3 = [
            renderWidget
        ];
        $[4] = renderWidget;
        $[5] = t2;
        $[6] = t3;
    } else {
        t2 = $[5];
        t3 = $[6];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t2, t3);
    if (!Component) {
        let t4;
        if ($[7] === Symbol.for("react.memo_cache_sentinel")) {
            t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__f__as__ShimmerEffect$3e$__["ShimmerEffect"], {
                height: "100%"
            });
            $[7] = t4;
        } else {
            t4 = $[7];
        }
        return t4;
    }
    let t4;
    if ($[8] !== Component) {
        t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["Fragment"], {
            children: Component
        });
        $[8] = Component;
        $[9] = t4;
    } else {
        t4 = $[9];
    }
    return t4;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/useDashboardLayout.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useDashboardLayout",
    ()=>useDashboardLayout
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$sortable$2f$dist$2f$sortable$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/sortable/dist/sortable.esm.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$preferences$2f$keys$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/preferences/keys.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$renderWidget$2f$RenderWidget$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/renderWidget/RenderWidget.js [app-client] (ecmascript)");
;
;
;
;
;
function useDashboardLayout(initialLayout) {
    const setLayoutPreference = useSetLayoutPreference();
    const [isEditing, setIsEditing] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    const { widgets = [] } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])().config.admin.dashboard ?? {};
    const [currentLayout, setCurrentLayout] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(initialLayout);
    const { openModal } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useModal"])();
    const cancelModalSlug = 'cancel-dashboard-changes';
    const { serverFunction } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useServerFunctions"])();
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    // Sync state when initialLayout prop changes (e.g., when query params change and server component re-renders)
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])({
        "useDashboardLayout.useEffect": ()=>{
            if (!isEditing) {
                setCurrentLayout(initialLayout);
            }
        // do not sync while editing. Depending on `isEditing` in this effect causes an
        // unintended rollback when toggling from editing -> view mode after save.
        }
    }["useDashboardLayout.useEffect"], [
        initialLayout
    ]);
    const saveLayout = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[saveLayout]": async ()=>{
            try {
                const layoutData = currentLayout.map({
                    "useDashboardLayout.useCallback[saveLayout].layoutData": (item)=>item.item
                }["useDashboardLayout.useCallback[saveLayout].layoutData"]);
                setIsEditing(false);
                await setLayoutPreference(layoutData);
            } catch  {
                setIsEditing(true);
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(t('error:failedToSaveLayout'));
            }
        }
    }["useDashboardLayout.useCallback[saveLayout]"], [
        setLayoutPreference,
        currentLayout
    ]);
    const resetLayout = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[resetLayout]": async ()=>{
            try {
                await setLayoutPreference(null);
                const result = await serverFunction({
                    name: 'get-default-layout',
                    args: {}
                });
                setCurrentLayout(result.layout);
                setIsEditing(false);
            } catch  {
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].error(t('error:failedToResetLayout'));
            }
        }
    }["useDashboardLayout.useCallback[resetLayout]"], [
        setLayoutPreference,
        serverFunction
    ]);
    const performCancel = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[performCancel]": ()=>{
            setCurrentLayout(initialLayout);
            setIsEditing(false);
        }
    }["useDashboardLayout.useCallback[performCancel]"], [
        initialLayout
    ]);
    const cancel = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[cancel]": ()=>{
            // Check if layout has changed
            const hasChanges = currentLayout.length !== initialLayout.length || currentLayout.some({
                "useDashboardLayout.useCallback[cancel]": (widget, index)=>{
                    const initialWidget = initialLayout[index];
                    return !initialWidget || widget.item.id !== initialWidget.item.id || widget.item.width !== initialWidget.item.width || JSON.stringify(widget.item.data || {}) !== JSON.stringify(initialWidget.item.data || {});
                }
            }["useDashboardLayout.useCallback[cancel]"]);
            // If there are changes, show confirmation modal
            if (hasChanges) {
                openModal(cancelModalSlug);
            } else {
                performCancel();
            }
        }
    }["useDashboardLayout.useCallback[cancel]"], [
        currentLayout,
        initialLayout,
        openModal,
        cancelModalSlug,
        performCancel
    ]);
    const moveWidget = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[moveWidget]": ({ moveFromIndex, moveToIndex })=>{
            if (moveFromIndex === moveToIndex || moveFromIndex < 0 || moveToIndex < 0) {
                return;
            }
            setCurrentLayout({
                "useDashboardLayout.useCallback[moveWidget]": (prev)=>{
                    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$sortable$2f$dist$2f$sortable$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["arrayMove"])(prev, moveFromIndex, moveToIndex);
                }
            }["useDashboardLayout.useCallback[moveWidget]"]);
        }
    }["useDashboardLayout.useCallback[moveWidget]"], []);
    const addWidget = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[addWidget]": (widgetSlug)=>{
            if (!isEditing) {
                return;
            }
            const widgetId = `${widgetSlug}-${Date.now()}`;
            const widget = widgets.find({
                "useDashboardLayout.useCallback[addWidget].widget": (widget)=>widget.slug === widgetSlug
            }["useDashboardLayout.useCallback[addWidget].widget"]);
            // Create a new widget instance using RenderWidget
            const newWidgetInstance = {
                component: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$renderWidget$2f$RenderWidget$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RenderWidget"], {
                    widgetData: {},
                    widgetId
                }),
                item: {
                    id: widgetId,
                    data: {},
                    maxWidth: widget?.maxWidth ?? 'full',
                    minWidth: widget?.minWidth ?? 'x-small',
                    width: widget?.minWidth ?? 'x-small'
                }
            };
            setCurrentLayout({
                "useDashboardLayout.useCallback[addWidget]": (prev)=>[
                        ...prev,
                        newWidgetInstance
                    ]
            }["useDashboardLayout.useCallback[addWidget]"]);
            // Scroll to the newly added widget after it's rendered and highlight it
            setTimeout({
                "useDashboardLayout.useCallback[addWidget]": ()=>{
                    const element = document.getElementById(widgetId);
                    if (element) {
                        element.scrollIntoView({
                            behavior: 'smooth',
                            block: 'center'
                        });
                        // Add highlight animation to the widget element
                        const widget = element.closest('.widget');
                        if (widget) {
                            widget.classList.add('widget--highlight');
                            // Remove the class after animation completes (1.5s fade out)
                            setTimeout({
                                "useDashboardLayout.useCallback[addWidget]": ()=>{
                                    widget.classList.remove('widget--highlight');
                                }
                            }["useDashboardLayout.useCallback[addWidget]"], 1500);
                        }
                    }
                }
            }["useDashboardLayout.useCallback[addWidget]"], 100);
        }
    }["useDashboardLayout.useCallback[addWidget]"], [
        isEditing,
        widgets
    ]);
    const deleteWidget = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[deleteWidget]": (widgetId)=>{
            if (!isEditing) {
                return;
            }
            setCurrentLayout({
                "useDashboardLayout.useCallback[deleteWidget]": (prev)=>prev.filter({
                        "useDashboardLayout.useCallback[deleteWidget]": (item)=>item.item.id !== widgetId
                    }["useDashboardLayout.useCallback[deleteWidget]"])
            }["useDashboardLayout.useCallback[deleteWidget]"]);
        }
    }["useDashboardLayout.useCallback[deleteWidget]"], [
        isEditing
    ]);
    const resizeWidget = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[resizeWidget]": (widgetId, newWidth)=>{
            if (!isEditing) {
                return;
            }
            setCurrentLayout({
                "useDashboardLayout.useCallback[resizeWidget]": (prev)=>prev.map({
                        "useDashboardLayout.useCallback[resizeWidget]": (item)=>item.item.id === widgetId ? {
                                ...item,
                                item: {
                                    ...item.item,
                                    width: newWidth
                                }
                            } : item
                    }["useDashboardLayout.useCallback[resizeWidget]"])
            }["useDashboardLayout.useCallback[resizeWidget]"]);
        }
    }["useDashboardLayout.useCallback[resizeWidget]"], [
        isEditing
    ]);
    const updateWidgetData = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useDashboardLayout.useCallback[updateWidgetData]": (widgetId, data)=>{
            if (!isEditing) {
                return;
            }
            setCurrentLayout({
                "useDashboardLayout.useCallback[updateWidgetData]": (prev)=>prev.map({
                        "useDashboardLayout.useCallback[updateWidgetData]": (item)=>item.item.id === widgetId ? {
                                component: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Dashboard$2f$Default$2f$ModularDashboard$2f$renderWidget$2f$RenderWidget$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["RenderWidget"], {
                                    widgetData: data,
                                    widgetId
                                }),
                                item: {
                                    ...item.item,
                                    data
                                }
                            } : item
                    }["useDashboardLayout.useCallback[updateWidgetData]"])
            }["useDashboardLayout.useCallback[updateWidgetData]"]);
        }
    }["useDashboardLayout.useCallback[updateWidgetData]"], [
        isEditing
    ]);
    const cancelModal = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].createElement(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmationModal"], {
        body: t('dashboard:discardMessage'),
        confirmLabel: t('dashboard:discardConfirmLabel'),
        heading: t('dashboard:discardTitle'),
        modalSlug: cancelModalSlug,
        onConfirm: performCancel
    });
    return {
        addWidget,
        cancel,
        cancelModal,
        currentLayout,
        deleteWidget,
        isEditing,
        moveWidget,
        resetLayout,
        resizeWidget,
        saveLayout,
        setIsEditing,
        updateWidgetData
    };
}
function useSetLayoutPreference() {
    const { setPreference } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["usePreferences"])();
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useCallback"])({
        "useSetLayoutPreference.useCallback": async (layout)=>{
            await setPreference(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$preferences$2f$keys$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["PREFERENCE_KEYS"].DASHBOARD_LAYOUT, {
                layouts: layout
            }, false);
        }
    }["useSetLayoutPreference.useCallback"], [
        setPreference
    ]);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/collisionDetection.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

/**
 * Collision detection that considers the X
 * axis only with respect to the position of the pointer (or collisionRect for keyboard)
 */ __turbopack_context__.s([
    "closestInXAxis",
    ()=>closestInXAxis
]);
const closestInXAxis = (args)=>{
    const collisions = [];
    // Use pointer coordinates if available (mouse/touch), otherwise use collisionRect center (keyboard)
    let x;
    let y;
    if (args.pointerCoordinates) {
        x = args.pointerCoordinates.x;
        y = args.pointerCoordinates.y;
    } else if (args.collisionRect) {
        // For keyboard navigation, use the center of the collisionRect
        x = args.collisionRect.left + args.collisionRect.width / 2;
        y = args.collisionRect.top + args.collisionRect.height / 2;
    } else {
        return [];
    }
    for (const container of args.droppableContainers){
        const rect = args.droppableRects.get(container.id);
        if (!rect) {
            continue;
        }
        // Only consider widgets in the same row (same Y axis)
        if (y >= rect.top && y <= rect.bottom) {
            const centerX = rect.left + rect.width / 2;
            const distance = Math.abs(x - centerX);
            collisions.push({
                id: String(container.id),
                data: {
                    value: distance
                }
            });
        }
    }
    return collisions.sort((a, b)=>a.data.value - b.data.value);
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/localeUtils.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "extractLocaleData",
    ()=>extractLocaleData,
    "mergeLocaleData",
    ()=>mergeLocaleData
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/config/types.js [app-client] (ecmascript)");
;
function isLocalized(field) {
    return 'localized' in field && Boolean(field.localized);
}
function getObjectValue(value) {
    return typeof value === 'object' && value !== null && !Array.isArray(value) ? value : {};
}
function extractLocaleData(widgetData, locale, fields) {
    const result = {};
    for (const field of fields){
        if (field.type === 'tabs') {
            for (const tab of field.tabs){
                const tabFields = tab.fields;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["tabHasName"])(tab)) {
                    result[tab.name] = extractLocaleData(getObjectValue(widgetData[tab.name]), locale, tabFields);
                } else {
                    Object.assign(result, extractLocaleData(widgetData, locale, tabFields));
                }
            }
            continue;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldHasSubFields"])(field) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field)) {
            Object.assign(result, extractLocaleData(widgetData, locale, field.fields));
            continue;
        }
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field)) {
            continue;
        }
        const { name } = field;
        const value = widgetData[name];
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldHasSubFields"])(field)) {
            result[name] = extractLocaleData(getObjectValue(value), locale, field.fields);
            continue;
        }
        if (isLocalized(field) && value !== undefined && typeof value === 'object' && value !== null && !Array.isArray(value)) {
            result[name] = value[locale];
        } else {
            result[name] = value;
        }
    }
    return result;
}
function mergeLocaleData(existingData, formData, locale, fields) {
    const result = {
        ...existingData
    };
    for (const field of fields){
        if (field.type === 'tabs') {
            for (const tab of field.tabs){
                const tabFields = tab.fields;
                if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["tabHasName"])(tab)) {
                    result[tab.name] = mergeLocaleData(getObjectValue(result[tab.name]), getObjectValue(formData[tab.name]), locale, tabFields);
                } else {
                    Object.assign(result, mergeLocaleData(result, formData, locale, tabFields));
                }
            }
            continue;
        }
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldHasSubFields"])(field) && !(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field)) {
            Object.assign(result, mergeLocaleData(result, formData, locale, field.fields));
            continue;
        }
        if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldAffectsData"])(field)) {
            continue;
        }
        const { name } = field;
        if ((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$config$2f$types$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["fieldHasSubFields"])(field)) {
            result[name] = mergeLocaleData(getObjectValue(result[name]), getObjectValue(formData[name]), locale, field.fields);
            continue;
        }
        if (isLocalized(field)) {
            result[name] = {
                ...getObjectValue(result[name]),
                [locale]: formData[name]
            };
        } else {
            result[name] = formData[name];
        }
    }
    return result;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Dashboard/Default/ModularDashboard/utils/sensors.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useDashboardSensors",
    ()=>useDashboardSensors
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@dnd-kit/core/dist/core.esm.js [app-client] (ecmascript)");
;
/**
 * Get all droppable widget positions, filtering out overlapping "before" droppables
 * and assigning row numbers based on Y position.
 */ function getDroppablePositions() {
    const positionTolerance = 5;
    const rowTolerance = 10;
    const result = [];
    let currentRow = 0;
    let currentY = null;
    const allDroppables = Array.from(document.querySelectorAll('.droppable-widget'));
    for(let i = 0; i < allDroppables.length; i++){
        const element = allDroppables[i];
        const rect = element.getBoundingClientRect();
        // Skip hidden elements
        if (rect.width === 0 || rect.height === 0) {
            continue;
        }
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const testId = element.getAttribute('data-testid') || '';
        const isBeforeDroppable = testId.endsWith('-before');
        // Skip "before" droppables that overlap with another droppable
        if (isBeforeDroppable) {
            const hasOverlapping = allDroppables.some((other, otherIndex)=>{
                if (otherIndex === i) {
                    return false;
                }
                const otherRect = other.getBoundingClientRect();
                const otherCenterX = otherRect.left + otherRect.width / 2;
                const otherCenterY = otherRect.top + otherRect.height / 2;
                return Math.abs(otherCenterX - centerX) < positionTolerance && Math.abs(otherCenterY - centerY) < positionTolerance;
            });
            if (hasOverlapping) {
                continue;
            }
        }
        // Assign row number based on Y position change
        if (currentY === null) {
            currentY = centerY;
        } else if (Math.abs(centerY - currentY) >= rowTolerance) {
            currentRow++;
            currentY = centerY;
        }
        result.push({
            centerX,
            centerY,
            element,
            isBeforeDroppable,
            rect,
            row: currentRow
        });
    }
    return result;
}
/**
 * Find the row with the closest Y position to the given posY.
 * Returns the row index, or null if no droppables exist.
 */ function findClosestRow(droppables, posY) {
    if (droppables.length === 0) {
        return null;
    }
    let closestRow = droppables[0].row;
    let minYDistance = Infinity;
    for (const droppable of droppables){
        const yDistance = Math.abs(droppable.centerY - posY);
        if (yDistance < minYDistance) {
            minYDistance = yDistance;
            closestRow = droppable.row;
        }
    }
    return closestRow;
}
/**
 * Find the closest droppable within a specific row by X position.
 * Returns the droppable and its index, or null if no droppables in that row.
 */ function findClosestDroppableInRow(droppables, rowIndex, posX) {
    let closestIndex = -1;
    let minXDistance = Infinity;
    for(let i = 0; i < droppables.length; i++){
        const droppable = droppables[i];
        if (droppable.row === rowIndex) {
            const xDistance = Math.abs(droppable.centerX - posX);
            if (xDistance < minXDistance) {
                minXDistance = xDistance;
                closestIndex = i;
            }
        }
    }
    if (closestIndex === -1) {
        return null;
    }
    return {
        droppable: droppables[closestIndex],
        index: closestIndex
    };
}
/**
 * Find the target droppable based on direction
 * - ArrowRight/Left: Next/previous in DOM order (now that overlapping droppables are filtered)
 * - ArrowUp/Down: Closest in adjacent row (row +1 or -1) by X position
 */ function findTargetDroppable(droppables, currentCenterX, currentCenterY, direction) {
    // Find the closest row, then the closest droppable in that row
    const currentRow = findClosestRow(droppables, currentCenterY);
    if (currentRow === null) {
        return null;
    }
    const currentDroppable = findClosestDroppableInRow(droppables, currentRow, currentCenterX);
    if (!currentDroppable) {
        return null;
    }
    const { index: currentIndex } = currentDroppable;
    switch(direction){
        case 'ArrowDown':
            {
                const targetRow = currentRow + 1;
                return findClosestDroppableInRow(droppables, targetRow, currentCenterX)?.droppable || null;
            }
        case 'ArrowLeft':
            // Previous in DOM order
            return droppables[currentIndex - 1] || null;
        case 'ArrowRight':
            // Next in DOM order
            return droppables[currentIndex + 1] || null;
        case 'ArrowUp':
            {
                const targetRow = currentRow - 1;
                return findClosestDroppableInRow(droppables, targetRow, currentCenterX)?.droppable || null;
            }
        default:
            return null;
    }
}
/**
 * Custom coordinate getter that jumps directly to droppable positions
 * instead of moving in pixel increments. This works better with scrolling
 * and provides more predictable navigation.
 */ const droppableJumpKeyboardCoordinateGetter = (event, { context, currentCoordinates })=>{
    const { collisionRect } = context;
    const { code } = event;
    if (!collisionRect) {
        return currentCoordinates;
    }
    // Only handle arrow keys
    if (![
        'ArrowDown',
        'ArrowLeft',
        'ArrowRight',
        'ArrowUp'
    ].includes(code)) {
        return currentCoordinates;
    }
    // Prevent default browser scroll behavior for arrow keys
    event.preventDefault();
    // Clear scrollableAncestors to prevent dnd-kit from scrolling instead of moving
    // This must be done on every keydown because context is updated by dnd-kit
    if (context.scrollableAncestors) {
        context.scrollableAncestors.length = 0;
    }
    // Get all droppable widgets and their positions
    const droppables = getDroppablePositions();
    if (droppables.length === 0) {
        return currentCoordinates;
    }
    // Current position center (viewport coordinates from collisionRect)
    const currentCenterX = collisionRect.left + collisionRect.width / 2;
    const currentCenterY = collisionRect.top + collisionRect.height / 2;
    // Find the target droppable based on direction
    const targetDroppable = findTargetDroppable(droppables, currentCenterX, currentCenterY, code);
    // If we found a target, scroll if needed and calculate the delta
    if (targetDroppable) {
        const viewportHeight = window.innerHeight;
        const targetRect = targetDroppable.rect;
        const scrollPadding = 20 // Extra padding to ensure element is fully visible
        ;
        // Check if target droppable is fully visible in viewport
        const isAboveViewport = targetRect.top < scrollPadding;
        const isBelowViewport = targetRect.bottom > viewportHeight - scrollPadding;
        // Scroll to make target visible (using instant scroll for synchronous behavior)
        if (isAboveViewport) {
            const scrollAmount = targetRect.top - scrollPadding;
            // don't use smooth scroll here, because it will mess up the delta calculation
            window.scrollBy({
                behavior: 'instant',
                top: scrollAmount
            });
        } else if (isBelowViewport) {
            const scrollAmount = targetRect.bottom - viewportHeight + scrollPadding;
            window.scrollBy({
                behavior: 'instant',
                top: scrollAmount
            });
        }
        // After scroll, recalculate target position (it may have changed due to scroll)
        const newTargetRect = targetDroppable.element.getBoundingClientRect();
        const newTargetCenterX = newTargetRect.left + newTargetRect.width / 2;
        const newTargetCenterY = newTargetRect.top + newTargetRect.height / 2;
        // Calculate delta using current overlay position (which didn't change) and new target position
        const deltaX = newTargetCenterX - currentCenterX;
        const deltaY = newTargetCenterY - currentCenterY;
        // Add delta to currentCoordinates to position overlay's center at target's center
        return {
            x: currentCoordinates.x + deltaX,
            y: currentCoordinates.y + deltaY
        };
    }
    // No valid target found, stay in place
    return currentCoordinates;
};
/**
 * Custom KeyboardSensor that only activates when focus is directly on the
 * draggable element, not on any of its descendants. This allows interactive
 * elements inside draggables (like buttons) to work normally with the keyboard.
 */ class DirectFocusKeyboardSensor extends __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardSensor"] {
    static activators = [
        {
            eventName: 'onKeyDown',
            handler: (event, { keyboardCodes = {
                cancel: [
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Esc
                ],
                end: [
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Space,
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Enter
                ],
                start: [
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Space,
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["KeyboardCode"].Enter
                ]
            }, onActivation }, { active })=>{
                const { code } = event.nativeEvent;
                // Only activate if focus is directly on the draggable node, not descendants
                if (event.target !== active.node.current) {
                    return false;
                }
                if (keyboardCodes.start.includes(code)) {
                    event.preventDefault();
                    onActivation?.({
                        event: event.nativeEvent
                    });
                    return true;
                }
                return false;
            }
        }
    ];
}
function useDashboardSensors() {
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSensors"])((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSensor"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["MouseSensor"], {
        activationConstraint: {
            distance: 5
        }
    }), (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSensor"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["TouchSensor"], {
        activationConstraint: {
            delay: 200,
            tolerance: 5
        }
    }), (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$dnd$2d$kit$2f$core$2f$dist$2f$core$2e$esm$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useSensor"])(DirectFocusKeyboardSensor, {
        coordinateGetter: droppableJumpKeyboardCoordinateGetter
    }));
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ForgotPassword/ForgotPasswordForm/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ForgotPasswordForm",
    ()=>ForgotPasswordForm
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/validations.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$elements$2f$FormHeader$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/elements/FormHeader/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const ForgotPasswordForm = ()=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(17);
    const { config, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t0, routes: t1 } = config;
    const { user: userSlug } = t0;
    const { api: apiRoute } = t1;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const [hasSubmitted, setHasSubmitted] = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useState"])(false);
    let t2;
    if ($[0] !== getEntityConfig || $[1] !== userSlug) {
        t2 = getEntityConfig({
            collectionSlug: userSlug
        });
        $[0] = getEntityConfig;
        $[1] = userSlug;
        $[2] = t2;
    } else {
        t2 = $[2];
    }
    const collectionConfig = t2;
    const loginWithUsername = collectionConfig?.auth?.loginWithUsername;
    let t3;
    if ($[3] !== loginWithUsername || $[4] !== t) {
        t3 = (res, successToast, errorToast)=>{
            res.json().then(()=>{
                setHasSubmitted(true);
                successToast(t("general:submissionSuccessful"));
            }).catch(()=>{
                errorToast(loginWithUsername ? t("authentication:usernameNotValid") : t("authentication:emailNotValid"));
            });
        };
        $[3] = loginWithUsername;
        $[4] = t;
        $[5] = t3;
    } else {
        t3 = $[5];
    }
    const handleResponse = t3;
    let t4;
    let t5;
    if ($[6] !== apiRoute || $[7] !== config || $[8] !== handleResponse || $[9] !== hasSubmitted || $[10] !== loginWithUsername || $[11] !== t || $[12] !== userSlug) {
        t5 = Symbol.for("react.early_return_sentinel");
        bb0: {
            const initialState = loginWithUsername ? {
                username: {
                    initialValue: "",
                    valid: true,
                    value: undefined
                }
            } : {
                email: {
                    initialValue: "",
                    valid: true,
                    value: undefined
                }
            };
            if (hasSubmitted) {
                let t6;
                if ($[15] !== t) {
                    t6 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$elements$2f$FormHeader$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormHeader"], {
                        description: t("authentication:checkYourEmailForPasswordReset"),
                        heading: t("authentication:emailSent")
                    });
                    $[15] = t;
                    $[16] = t6;
                } else {
                    t6 = $[16];
                }
                t5 = t6;
                break bb0;
            }
            t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
                action: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                    apiRoute,
                    path: `/${userSlug}/forgot-password`
                }),
                handleResponse,
                initialState,
                method: "POST",
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$elements$2f$FormHeader$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["FormHeader"], {
                        description: loginWithUsername ? t("authentication:forgotPasswordUsernameInstructions") : t("authentication:forgotPasswordEmailInstructions"),
                        heading: t("authentication:forgotPassword")
                    }),
                    loginWithUsername ? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["TextField"], {
                        field: {
                            name: "username",
                            label: t("authentication:username"),
                            required: true
                        },
                        path: "username",
                        validate: (value)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["text"])(value, {
                                name: "username",
                                type: "text",
                                blockData: {},
                                data: {},
                                event: "onChange",
                                path: [
                                    "username"
                                ],
                                preferences: {
                                    fields: {}
                                },
                                req: {
                                    payload: {
                                        config
                                    },
                                    t
                                },
                                required: true,
                                siblingData: {}
                            })
                    }) : (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EmailField"], {
                        field: {
                            name: "email",
                            admin: {
                                autoComplete: "email"
                            },
                            label: t("general:email"),
                            required: true
                        },
                        path: "email",
                        validate: (value_0)=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["email"])(value_0, {
                                name: "email",
                                type: "email",
                                blockData: {},
                                data: {},
                                event: "onChange",
                                path: [
                                    "email"
                                ],
                                preferences: {
                                    fields: {}
                                },
                                req: {
                                    payload: {
                                        config
                                    },
                                    t
                                },
                                required: true,
                                siblingData: {}
                            })
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FormSubmit"], {
                        size: "large",
                        children: t("general:submit")
                    })
                ]
            });
        }
        $[6] = apiRoute;
        $[7] = config;
        $[8] = handleResponse;
        $[9] = hasSubmitted;
        $[10] = loginWithUsername;
        $[11] = t;
        $[12] = userSlug;
        $[13] = t4;
        $[14] = t5;
    } else {
        t4 = $[13];
        t5 = $[14];
    }
    if (t5 !== Symbol.for("react.early_return_sentinel")) {
        return t5;
    }
    return t4;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Login/LoginField/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LoginField",
    ()=>LoginField
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/fields/validations.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
const LoginField = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    const { type, required: t1 } = t0;
    const required = t1 === undefined ? true : t1;
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    if (type === "email") {
        let t2;
        if ($[0] !== required || $[1] !== t) {
            t2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["EmailField"], {
                field: {
                    name: "email",
                    admin: {
                        autoComplete: "email"
                    },
                    label: t("general:email"),
                    required
                },
                path: "email",
                validate: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["email"]
            });
            $[0] = required;
            $[1] = t;
            $[2] = t2;
        } else {
            t2 = $[2];
        }
        return t2;
    }
    if (type === "username") {
        let t2;
        if ($[3] !== required || $[4] !== t) {
            t2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["TextField"], {
                field: {
                    name: "username",
                    label: t("authentication:username"),
                    required
                },
                path: "username",
                validate: __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["username"]
            });
            $[3] = required;
            $[4] = t;
            $[5] = t2;
        } else {
            t2 = $[5];
        }
        return t2;
    }
    if (type === "emailOrUsername") {
        let t2;
        if ($[6] !== required || $[7] !== t) {
            let t3;
            if ($[9] !== t) {
                t3 = (value, options)=>{
                    const passesUsername = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["username"])(value, options);
                    const passesEmail = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$fields$2f$validations$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["email"])(value, options);
                    if (!passesEmail && !passesUsername) {
                        return `${t("general:email")}: ${passesEmail} ${t("general:username")}: ${passesUsername}`;
                    }
                    return true;
                };
                $[9] = t;
                $[10] = t3;
            } else {
                t3 = $[10];
            }
            t2 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["TextField"], {
                field: {
                    name: "username",
                    label: t("authentication:emailOrUsername"),
                    required
                },
                path: "username",
                validate: t3
            });
            $[6] = required;
            $[7] = t;
            $[8] = t2;
        } else {
            t2 = $[8];
        }
        return t2;
    }
    return null;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Login/LoginForm/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LoginForm",
    ()=>LoginForm
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$getLoginOptions$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/auth/getLoginOptions.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$getSafeRedirect$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getSafeRedirect.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Login$2f$LoginField$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Login/LoginField/index.js [app-client] (ecmascript)");
'use client';
;
;
;
const baseClass = 'login__form';
;
;
;
const LoginForm = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(23);
    const { prefillEmail, prefillPassword, prefillUsername, searchParams } = t0;
    const { config, getEntityConfig } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t1, routes: t2 } = config;
    const { routes: t3, user: userSlug } = t1;
    const { forgot: forgotRoute } = t3;
    const { admin: adminRoute, api: apiRoute } = t2;
    let loginWithUsername;
    let t4;
    if ($[0] !== getEntityConfig || $[1] !== userSlug) {
        const collectionConfig = getEntityConfig({
            collectionSlug: userSlug
        });
        const { auth: authOptions } = collectionConfig;
        loginWithUsername = authOptions.loginWithUsername;
        t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$auth$2f$getLoginOptions$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getLoginOptions"])(loginWithUsername);
        $[0] = getEntityConfig;
        $[1] = userSlug;
        $[2] = loginWithUsername;
        $[3] = t4;
    } else {
        loginWithUsername = $[2];
        t4 = $[3];
    }
    const { canLoginWithEmail, canLoginWithUsername } = t4;
    let t5;
    if ($[4] !== canLoginWithEmail || $[5] !== canLoginWithUsername) {
        t5 = ()=>{
            if (canLoginWithEmail && canLoginWithUsername) {
                return "emailOrUsername";
            }
            if (canLoginWithUsername) {
                return "username";
            }
            return "email";
        };
        $[4] = canLoginWithEmail;
        $[5] = canLoginWithUsername;
        $[6] = t5;
    } else {
        t5 = $[6];
    }
    const [loginType] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(t5);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { setUser } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAuth"])();
    const t6 = prefillPassword ?? undefined;
    const t7 = prefillPassword ?? undefined;
    let t8;
    if ($[7] !== adminRoute || $[8] !== apiRoute || $[9] !== forgotRoute || $[10] !== loginType || $[11] !== loginWithUsername || $[12] !== prefillEmail || $[13] !== prefillUsername || $[14] !== searchParams?.redirect || $[15] !== setUser || $[16] !== t || $[17] !== t6 || $[18] !== t7 || $[19] !== userSlug) {
        const initialState = {
            password: {
                initialValue: t6,
                valid: true,
                value: t7
            }
        };
        if (loginWithUsername) {
            initialState.username = {
                initialValue: prefillUsername ?? undefined,
                valid: true,
                value: prefillUsername ?? undefined
            };
        } else {
            initialState.email = {
                initialValue: prefillEmail ?? undefined,
                valid: true,
                value: prefillEmail ?? undefined
            };
        }
        let t9;
        if ($[21] !== setUser) {
            t9 = (data)=>{
                setUser(data);
            };
            $[21] = setUser;
            $[22] = t9;
        } else {
            t9 = $[22];
        }
        const handleLogin = t9;
        t8 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
            action: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute,
                path: `/${userSlug}/login`
            }),
            className: baseClass,
            disableSuccessStatus: true,
            initialState,
            method: "POST",
            onSuccess: handleLogin,
            redirect: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$getSafeRedirect$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["getSafeRedirect"])({
                fallbackTo: adminRoute,
                redirectTo: searchParams?.redirect
            }),
            waitForAutocomplete: true,
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                    className: `${baseClass}__inputWrap`,
                    children: [
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$next$2f$dist$2f$views$2f$Login$2f$LoginField$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["LoginField"], {
                            type: loginType
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PasswordField"], {
                            field: {
                                name: "password",
                                label: t("general:password"),
                                required: true
                            },
                            path: "password"
                        })
                    ]
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Link"], {
                    href: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                        adminRoute,
                        path: forgotRoute
                    }),
                    prefetch: false,
                    children: t("authentication:forgotPasswordQuestion")
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FormSubmit"], {
                    size: "large",
                    children: t("authentication:login")
                })
            ]
        });
        $[7] = adminRoute;
        $[8] = apiRoute;
        $[9] = forgotRoute;
        $[10] = loginType;
        $[11] = loginWithUsername;
        $[12] = prefillEmail;
        $[13] = prefillUsername;
        $[14] = searchParams?.redirect;
        $[15] = setUser;
        $[16] = t;
        $[17] = t6;
        $[18] = t7;
        $[19] = userSlug;
        $[20] = t8;
    } else {
        t8 = $[20];
    }
    return t8;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Logout/LogoutClient.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "LogoutClient",
    ()=>LogoutClient
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const baseClass = 'logout';
const LogoutClient = (props)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(23);
    const { adminRoute, inactivity, redirect } = props;
    const { logOut, user } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAuth"])();
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useRouteTransition"])();
    user?.id;
    const isLoggedIn = Boolean(user?.id);
    const navigatingToLoginRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useRef(false);
    let t0;
    if ($[0] !== adminRoute || $[1] !== inactivity || $[2] !== redirect) {
        t0 = ()=>(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                adminRoute,
                path: `/login${inactivity && redirect && redirect.length > 0 ? `?redirect=${encodeURIComponent(redirect)}` : ""}`
            });
        $[0] = adminRoute;
        $[1] = inactivity;
        $[2] = redirect;
        $[3] = t0;
    } else {
        t0 = $[3];
    }
    const [loginRoute] = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useState(t0);
    const { t } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    let t1;
    if ($[4] !== logOut || $[5] !== loginRoute || $[6] !== router || $[7] !== startRouteTransition || $[8] !== t) {
        t1 = async ()=>{
            if (!navigatingToLoginRef.current) {
                navigatingToLoginRef.current = true;
                await logOut();
                __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].success(t("authentication:loggedOutSuccessfully"));
                startRouteTransition(()=>router.push(loginRoute));
                return;
            }
        };
        $[4] = logOut;
        $[5] = loginRoute;
        $[6] = router;
        $[7] = startRouteTransition;
        $[8] = t;
        $[9] = t1;
    } else {
        t1 = $[9];
    }
    const handleLogOut = t1;
    let t2;
    let t3;
    if ($[10] !== handleLogOut || $[11] !== inactivity || $[12] !== isLoggedIn || $[13] !== loginRoute || $[14] !== router || $[15] !== startRouteTransition) {
        t2 = ()=>{
            if (isLoggedIn && !inactivity) {
                handleLogOut();
            } else {
                if (!navigatingToLoginRef.current) {
                    navigatingToLoginRef.current = true;
                    startRouteTransition(()=>router.push(loginRoute));
                }
            }
        };
        t3 = [
            handleLogOut,
            isLoggedIn,
            loginRoute,
            router,
            startRouteTransition,
            inactivity
        ];
        $[10] = handleLogOut;
        $[11] = inactivity;
        $[12] = isLoggedIn;
        $[13] = loginRoute;
        $[14] = router;
        $[15] = startRouteTransition;
        $[16] = t2;
        $[17] = t3;
    } else {
        t2 = $[16];
        t3 = $[17];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t2, t3);
    if (!isLoggedIn && inactivity) {
        let t4;
        if ($[18] !== loginRoute || $[19] !== t) {
            t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                className: `${baseClass}__wrap`,
                children: [
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])("h2", {
                        children: t("authentication:loggedOutInactivity")
                    }),
                    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Button"], {
                        buttonStyle: "secondary",
                        el: "link",
                        size: "large",
                        url: loginRoute,
                        children: t("authentication:logBackIn")
                    })
                ]
            });
            $[18] = loginRoute;
            $[19] = t;
            $[20] = t4;
        } else {
            t4 = $[20];
        }
        return t4;
    }
    let t4;
    if ($[21] !== t) {
        t4 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["LoadingOverlay"], {
            animationDuration: "0ms",
            loadingText: t("authentication:loggingOut")
        });
        $[21] = t;
        $[22] = t4;
    } else {
        t4 = $[22];
    }
    return t4;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/ResetPassword/ResetPasswordForm/index.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ResetPasswordForm",
    ()=>ResetPasswordForm
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/jsx-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export c as useConfig>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export d as useTranslation>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/formatAdminURL.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
;
;
const ResetPasswordForm = (t0)=>{
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(11);
    const { token } = t0;
    const i18n = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__d__as__useTranslation$3e$__["useTranslation"])();
    const { config: t1 } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$export__c__as__useConfig$3e$__["useConfig"])();
    const { admin: t2, routes: t3 } = t1;
    const { routes: t4, user: userSlug } = t2;
    const { login: loginRoute } = t4;
    const { admin: adminRoute, api: apiRoute } = t3;
    const history = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const { fetchFullUser } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useAuth"])();
    let t5;
    if ($[0] !== adminRoute || $[1] !== fetchFullUser || $[2] !== history || $[3] !== loginRoute) {
        t5 = async ()=>{
            const user = await fetchFullUser();
            if (user) {
                history.push(adminRoute);
            } else {
                history.push((0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                    adminRoute,
                    path: loginRoute
                }));
            }
        };
        $[0] = adminRoute;
        $[1] = fetchFullUser;
        $[2] = history;
        $[3] = loginRoute;
        $[4] = t5;
    } else {
        t5 = $[4];
    }
    const onSuccess = t5;
    let t6;
    if ($[5] !== apiRoute || $[6] !== i18n || $[7] !== onSuccess || $[8] !== token || $[9] !== userSlug) {
        const initialState = {
            "confirm-password": {
                initialValue: "",
                valid: false,
                value: ""
            },
            password: {
                initialValue: "",
                valid: false,
                value: ""
            },
            token: {
                initialValue: token,
                valid: true,
                value: token
            }
        };
        t6 = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["Form"], {
            action: (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$payload$2f$dist$2f$utilities$2f$formatAdminURL$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["formatAdminURL"])({
                apiRoute,
                path: `/${userSlug}/reset-password`
            }),
            initialState,
            method: "POST",
            onSuccess,
            children: [
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsxs"])("div", {
                    className: "inputWrap",
                    children: [
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["PasswordField"], {
                            field: {
                                name: "password",
                                label: i18n.t("authentication:newPassword"),
                                required: true
                            },
                            path: "password",
                            schemaPath: `${userSlug}.password`
                        }),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["ConfirmPasswordField"], {}),
                        (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["HiddenField"], {
                            path: "token",
                            schemaPath: `${userSlug}.token`,
                            value: token
                        })
                    ]
                }),
                (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$jsx$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["jsx"])(__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["FormSubmit"], {
                    size: "large",
                    children: i18n.t("authentication:resetPassword")
                })
            ]
        });
        $[5] = apiRoute;
        $[6] = i18n;
        $[7] = onSuccess;
        $[8] = token;
        $[9] = userSlug;
        $[10] = t6;
    } else {
        t6 = $[10];
    }
    return t6;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/next/dist/views/Verify/index.client.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "ToastAndRedirect",
    ()=>ToastAndRedirect
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/compiler-runtime.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/index.js [app-client] (ecmascript) <locals>");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/navigation.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/next/dist/compiled/react/index.js [app-client] (ecmascript)");
'use client';
;
;
;
;
function ToastAndRedirect(t0) {
    const $ = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$compiler$2d$runtime$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["c"])(6);
    const { message, redirectTo } = t0;
    const router = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$navigation$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useRouter"])();
    const { startRouteTransition } = (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["useRouteTransition"])();
    const hasToastedRef = __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].useRef(false);
    let t1;
    let t2;
    if ($[0] !== message || $[1] !== redirectTo || $[2] !== router || $[3] !== startRouteTransition) {
        t1 = ()=>{
            let timeoutID;
            if (__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"]) {
                timeoutID = setTimeout(()=>{
                    __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__$3c$locals$3e$__["toast"].success(message);
                    hasToastedRef.current = true;
                    startRouteTransition(()=>router.push(redirectTo));
                }, 100);
            }
            return ()=>{
                if (timeoutID) {
                    clearTimeout(timeoutID);
                }
            };
        };
        t2 = [
            router,
            redirectTo,
            message,
            startRouteTransition
        ];
        $[0] = message;
        $[1] = redirectTo;
        $[2] = router;
        $[3] = startRouteTransition;
        $[4] = t1;
        $[5] = t2;
    } else {
        t1 = $[4];
        t2 = $[5];
    }
    (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$next$2f$dist$2f$compiled$2f$react$2f$index$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["useEffect"])(t1, t2);
    return null;
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript) <export j as useTheme>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "useTheme",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["j"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$2GZJJKQF$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-2GZJJKQF.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript) <export a as XIcon>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "XIcon",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["a"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f40$payloadcms$2f$ui$2f$dist$2f$exports$2f$client$2f$chunk$2d$B52EQI3B$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/@payloadcms/ui/dist/exports/client/chunk-B52EQI3B.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/auth/getLoginOptions.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getLoginOptions",
    ()=>getLoginOptions
]);
const getLoginOptions = (loginWithUsername)=>{
    return {
        canLoginWithEmail: !loginWithUsername || loginWithUsername.allowEmailLogin,
        canLoginWithUsername: Boolean(loginWithUsername)
    };
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/payload/dist/utilities/getSafeRedirect.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "getSafeRedirect",
    ()=>getSafeRedirect
]);
const getSafeRedirect = ({ allowAbsoluteUrls = false, fallbackTo = '/', redirectTo })=>{
    if (typeof redirectTo !== 'string') {
        return fallbackTo;
    }
    const redirectPath = redirectTo.trim();
    const hasControlCharacters = [
        ...redirectPath
    ].some((character)=>{
        const code = character.charCodeAt(0);
        return code <= 31 || code === 127;
    });
    const hasAmbiguousPathPrefix = /^\/%(?:25)*(?:09|0a|0d|2f|5c)/i.test(redirectPath);
    let parsedRedirect;
    try {
        parsedRedirect = new URL(redirectPath, 'http://localhost');
    } catch  {
        return fallbackTo;
    }
    const isSafeRedirect = !hasControlCharacters && !hasAmbiguousPathPrefix && // Must start with a single forward slash (e.g., "/admin")
    redirectPath.startsWith('/') && // Must resolve to the same origin after URL parser normalization
    parsedRedirect.origin === 'http://localhost' && // Prevent protocol-relative URLs (e.g., "//example.com")
    !redirectPath.startsWith('//') && // Prevent encoded slashes that could resolve to protocol-relative
    !redirectPath.startsWith('/%2F') && // Prevent backslash-based escape attempts (e.g., "/\\/example.com", "/\\\\example.com", "/\\example.com")
    !redirectPath.startsWith('/\\/') && !redirectPath.startsWith('/\\\\') && !redirectPath.startsWith('/\\') && // Prevent javascript-based schemes (e.g., "/javascript:alert(1)")
    !redirectPath.toLowerCase().startsWith('/javascript:') && // Prevent attempts to redirect to full URLs using "/http:" or "/https:"
    !redirectPath.toLowerCase().startsWith('/http');
    const isAbsoluteSafeRedirect = allowAbsoluteUrls && !hasControlCharacters && // Must be a valid absolute URL with http or https
    /^https?:\/\/\S+$/i.test(redirectPath) && (parsedRedirect.protocol === 'http:' || parsedRedirect.protocol === 'https:');
    return isSafeRedirect || isAbsoluteSafeRedirect ? redirectPath : fallbackTo;
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/native.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
const randomUUID = typeof crypto !== 'undefined' && crypto.randomUUID && crypto.randomUUID.bind(crypto);
const __TURBOPACK__default__export__ = {
    randomUUID
};
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/regex.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
const __TURBOPACK__default__export__ = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}|00000000-0000-0000-0000-000000000000|ffffffff-ffff-ffff-ffff-ffffffffffff)$/i;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/rng.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>rng
]);
let getRandomValues;
const rnds8 = new Uint8Array(16);
function rng() {
    if (!getRandomValues) {
        if (typeof crypto === 'undefined' || !crypto.getRandomValues) {
            throw new Error('crypto.getRandomValues() not supported. See https://github.com/uuidjs/uuid#getrandomvalues-not-supported');
        }
        getRandomValues = crypto.getRandomValues.bind(crypto);
    }
    return getRandomValues(rnds8);
}
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/stringify.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__,
    "unsafeStringify",
    ()=>unsafeStringify
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$validate$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/validate.js [app-client] (ecmascript)");
;
const byteToHex = [];
for(let i = 0; i < 256; ++i){
    byteToHex.push((i + 0x100).toString(16).slice(1));
}
function unsafeStringify(arr, offset = 0) {
    return (byteToHex[arr[offset + 0]] + byteToHex[arr[offset + 1]] + byteToHex[arr[offset + 2]] + byteToHex[arr[offset + 3]] + '-' + byteToHex[arr[offset + 4]] + byteToHex[arr[offset + 5]] + '-' + byteToHex[arr[offset + 6]] + byteToHex[arr[offset + 7]] + '-' + byteToHex[arr[offset + 8]] + byteToHex[arr[offset + 9]] + '-' + byteToHex[arr[offset + 10]] + byteToHex[arr[offset + 11]] + byteToHex[arr[offset + 12]] + byteToHex[arr[offset + 13]] + byteToHex[arr[offset + 14]] + byteToHex[arr[offset + 15]]).toLowerCase();
}
function stringify(arr, offset = 0) {
    const uuid = unsafeStringify(arr, offset);
    if (!(0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$validate$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])(uuid)) {
        throw TypeError('Stringified UUID is invalid');
    }
    return uuid;
}
const __TURBOPACK__default__export__ = stringify;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/v4.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$native$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/native.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$rng$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/rng.js [app-client] (ecmascript)");
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$stringify$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/stringify.js [app-client] (ecmascript)");
;
;
;
function _v4(options, buf, offset) {
    options = options || {};
    const rnds = options.random ?? options.rng?.() ?? (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$rng$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"])();
    if (rnds.length < 16) {
        throw new Error('Random bytes length must be >= 16');
    }
    rnds[6] = rnds[6] & 0x0f | 0x40;
    rnds[8] = rnds[8] & 0x3f | 0x80;
    if (buf) {
        offset = offset || 0;
        if (offset < 0 || offset + 16 > buf.length) {
            throw new RangeError(`UUID byte range ${offset}:${offset + 15} is out of buffer bounds`);
        }
        for(let i = 0; i < 16; ++i){
            buf[offset + i] = rnds[i];
        }
        return buf;
    }
    return (0, __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$stringify$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["unsafeStringify"])(rnds);
}
function v4(options, buf, offset) {
    if (__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$native$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].randomUUID && !buf && !options) {
        return __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$native$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].randomUUID();
    }
    return _v4(options, buf, offset);
}
const __TURBOPACK__default__export__ = v4;
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/v4.js [app-client] (ecmascript) <export default as v4>", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "v4",
    ()=>__TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$v4$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"]
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$v4$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/v4.js [app-client] (ecmascript)");
}),
"[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/validate.js [app-client] (ecmascript)", ((__turbopack_context__) => {
"use strict";

__turbopack_context__.s([
    "default",
    ()=>__TURBOPACK__default__export__
]);
var __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$regex$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__ = __turbopack_context__.i("[project]/blueprints/payload-next-multisite/app/node_modules/uuid/dist/regex.js [app-client] (ecmascript)");
;
function validate(uuid) {
    return typeof uuid === 'string' && __TURBOPACK__imported__module__$5b$project$5d2f$blueprints$2f$payload$2d$next$2d$multisite$2f$app$2f$node_modules$2f$uuid$2f$dist$2f$regex$2e$js__$5b$app$2d$client$5d$__$28$ecmascript$29$__["default"].test(uuid);
}
const __TURBOPACK__default__export__ = validate;
}),
]);

//# sourceMappingURL=0nrf_0j4kwik._.js.map