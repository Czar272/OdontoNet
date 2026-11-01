# OdontoNet — Frontend

Aplicación web React + TypeScript + Vite + Tailwind CSS.

La instalación, configuración y ejecución están documentadas en [`docs/DEVELOPMENT.md`](../docs/DEVELOPMENT.md); la arquitectura, en [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Estructura de `src/`

| Carpeta | Contenido |
| --- | --- |
| `components/basic/` | Componentes genéricos de UI (Button, Input, Modal, Table, Card...). |
| `components/<dominio>/` | Componentes específicos de un módulo (p. ej. `patients/`). |
| `context/` | Contextos de React (sesión). |
| `layouts/` | Estructuras de página (sidebar + contenido). |
| `pages/` | Páginas asociadas a rutas. |
| `routes/` | Router y rutas protegidas. |
| `services/` | Cliente HTTP (Axios) y llamadas a la API. |
| `types/` | Tipos TypeScript del dominio. |

## Scripts

```powershell
npm run dev      # servidor de desarrollo (http://localhost:5173)
npm run lint     # ESLint
npm run build    # tsc + build de producción
```
