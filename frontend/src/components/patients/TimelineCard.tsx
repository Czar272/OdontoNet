import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import {
  CalendarCheck,
  ClipboardList,
  HeartPulse,
  Image as ImageIcon,
  Activity,
  ListOrdered,
  Stethoscope,
} from "lucide-react";
import clsx from "clsx";

import Button from "../basic/Button";
import Card from "../basic/Card";
import LoadingSpinner from "../basic/LoadingSpinner";
import { getTimeline } from "../../services/timelineService";
import type { TimelineEvent, TimelineEventType } from "../../types/timeline";
import { TIMELINE_TYPES, timelineKey } from "./timelineEvents";

const dateTime = new Intl.DateTimeFormat("es-GT", {
  dateStyle: "long",
  timeStyle: "short",
});

const ICONS: Record<TimelineEventType, typeof Stethoscope> = {
  visit: Stethoscope,
  treatment: ClipboardList,
  medical_history: HeartPulse,
  appointment: CalendarCheck,
  image: ImageIcon,
  periodontal: Activity,
};

const ICON_STYLES: Record<TimelineEventType, string> = {
  visit: "bg-blue-100 text-blue-700",
  treatment: "bg-amber-100 text-amber-700",
  medical_history: "bg-rose-100 text-rose-700",
  appointment: "bg-green-100 text-green-700",
  image: "bg-violet-100 text-violet-700",
  periodontal: "bg-teal-100 text-teal-700",
};

function EventItem({ event }: { event: TimelineEvent }) {
  const Icon = ICONS[event.type];
  const muted =
    event.voided ||
    event.action === "voided" ||
    event.action === "no_show" ||
    event.action === "cancelled";

  return (
    <li className="relative flex gap-4 pb-6 last:pb-0">
      <span
        className={clsx(
          "z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          ICON_STYLES[event.type],
        )}
        aria-hidden="true"
      >
        <Icon size={16} />
      </span>
      <div className="min-w-0">
        <p
          className={clsx(
            "font-medium",
            event.voided && "line-through text-gray-500",
          )}
        >
          {event.title}
        </p>
        <p className="text-sm text-gray-500">
          {dateTime.format(new Date(event.occurred_at))}
          {event.actor && ` · ${event.actor.name}`}
          {event.voided && " · anulada"}
        </p>
        {event.detail && (
          <p
            className={clsx(
              "text-sm mt-1 whitespace-pre-line",
              muted ? "text-gray-500" : "text-gray-800",
            )}
          >
            {event.detail}
          </p>
        )}
      </div>
    </li>
  );
}

/**
 * Historial cronológico del paciente (ODON-162): consultas, tratamientos,
 * historia médica y citas en una sola línea de tiempo, por páginas de 20.
 */
export default function TimelineCard({ patientId }: { patientId: number }) {
  const [types, setTypes] = useState<TimelineEventType[]>(
    TIMELINE_TYPES.map((t) => t.type),
  );

  const query = useInfiniteQuery({
    queryKey: [...timelineKey(patientId), types],
    queryFn: ({ pageParam }) =>
      getTimeline(patientId, { types, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: types.length > 0,
  });

  const toggle = (type: TimelineEventType) =>
    setTypes((current) =>
      current.includes(type)
        ? current.filter((t) => t !== type)
        : [...current, type],
    );

  const events = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <ListOrdered size={20} /> Historial cronológico
        </h2>
        <fieldset className="flex flex-wrap gap-3" aria-label="Mostrar">
          {TIMELINE_TYPES.map(({ type, label }) => (
            <label
              key={type}
              className="flex items-center gap-1.5 text-sm text-gray-700 select-none"
            >
              <input
                type="checkbox"
                checked={types.includes(type)}
                onChange={() => toggle(type)}
                className="h-4 w-4 accent-gray-900"
              />
              {label}
            </label>
          ))}
        </fieldset>
      </div>

      {types.length === 0 ? (
        <p className="text-sm text-gray-500">
          Elige al menos un tipo de evento.
        </p>
      ) : query.isLoading ? (
        <LoadingSpinner />
      ) : query.isError ? (
        <p className="text-sm text-red-600">No se pudo cargar el historial.</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-gray-500">
          Todavía no hay eventos en el historial de este paciente.
        </p>
      ) : (
        <>
          <ol
            aria-label="Historial cronológico"
            className="relative before:absolute before:left-4 before:top-2 before:bottom-2 before:w-px before:bg-gray-200"
          >
            {events.map((event) => (
              <EventItem key={event.id} event={event} />
            ))}
          </ol>
          {query.hasNextPage && (
            <div className="mt-6 flex justify-center">
              <Button
                variant="secondary"
                onClick={() => query.fetchNextPage()}
                disabled={query.isFetchingNextPage}
              >
                {query.isFetchingNextPage ? "Cargando..." : "Ver más"}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
