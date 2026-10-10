export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null || value === false) {
      continue;
    }
    if (key.startsWith("on")) {
      node.addEventListener(key.slice(2), value);
    } else if (key === "value") {
      node.value = value;
    } else {
      node.setAttribute(key, value === true ? "" : value);
    }
  }
  node.append(...children.flat().filter((child) => child != null && child !== false));
  return node;
}
