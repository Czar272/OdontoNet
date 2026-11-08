import { useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Button from "../../components/basic/Button";
import Card from "../../components/basic/Card";
import Input from "../../components/basic/Input";
import LoadingSpinner from "../../components/basic/LoadingSpinner";
import PageHeader from "../../components/basic/PageHeader";
import Select from "../../components/basic/Select";
import { useAuth } from "../../context/AuthContext";
import { getAuditEvents } from "../../services/auditService";
import { getUsers } from "../../services/userService";
import { ROLE_LABELS } from "../../types/auth";
import { ACTION_LABELS, actionLabel, entityLabel, fieldsLabel } from "./auditLabels";

/**
 * Auditoría (ODON-222): quién cambió o exportó qué y cuándo. Administración
 * ve toda la clínica y puede filtrar por usuario; un doctor ve solo sus
 * acciones. No muestra valores, solo los nombres de los campos cambiados.
 */
export default function AuditPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [action, setAction] = useState("");
  const [actorUserId, setActorUserId] = useState<number | null>(null);

  const { data: users } = useQuery({ queryKey: ["users"], queryFn: () => getUsers(), enabled: isAdmin });

  const filters = { from, to, action, actorUserId: isAdmin ? actorUserId : null };
  const query = useInfiniteQuery({
    queryKey: ["audit", filters],
    queryFn: ({ pageParam }) => getAuditEvents({ ...filters, cursor: pageParam }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: !from || !to || from <= to,
  });
  const events = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div>
      <PageHeader
        title="Auditoría"
        description={
          isAdmin
            ? "Quién cambió o exportó qué en la clínica. Los registros no se pueden editar ni borrar."
            : "Tus cambios y exportaciones. Los registros no se pueden editar ni borrar."
        }
      />

      <div className="flex flex-wrap items-end gap-4 mb-6">
        <div className="w-44">
          <Input label="Desde" type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </div>
        <div className="w-44">
          <Input label="Hasta" type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </div>
        <div className="w-72">
          <Select label="Acción" value={action} onChange={(event) => setAction(event.target.value)}>
            <option value="">Todas las acciones</option>
            {Object.entries(ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {isAdmin && (
          <div className="w-64">
            <Select
              label="Usuario"
              value={actorUserId ?? ""}
              onChange={(event) => setActorUserId(event.target.value ? Number(event.target.value) : null)}
            >
              <option value="">Todos los usuarios</option>
              {(users ?? []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
          </div>
        )}
      </div>

      {from && to && from > to && (
        <p role="alert" className="text-sm text-red-600 mb-6">
          La fecha final no puede ser anterior a la inicial.
        </p>
      )}

      <Card>
        {query.isLoading ? (
          <LoadingSpinner />
        ) : query.isError ? (
          <p role="alert" className="text-red-600">
            No se pudo cargar la auditoría.
          </p>
        ) : events.length === 0 ? (
          <p className="text-gray-500">No hay eventos con estos filtros.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm" aria-label="Eventos de auditoría">
              <thead>
                <tr className="text-left text-gray-500">
                  <th className="py-2 pr-4 font-medium">Fecha y hora</th>
                  <th className="py-2 pr-4 font-medium">Usuario</th>
                  <th className="py-2 pr-4 font-medium">Acción</th>
                  <th className="py-2 pr-4 font-medium">Registro</th>
                  <th className="py-2 pr-4 font-medium">Campos</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {events.map((event) => (
                  <tr key={event.id}>
                    <td className="py-2 pr-4 whitespace-nowrap tabular-nums">
                      {new Date(event.occurred_at).toLocaleString("es-GT", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </td>
                    <td className="py-2 pr-4">
                      {event.actor.name}
                      <span className="block text-xs text-gray-500">{ROLE_LABELS[event.actor.role]}</span>
                    </td>
                    <td className="py-2 pr-4">{actionLabel(event.action)}</td>
                    <td className="py-2 pr-4">
                      {entityLabel(event.entity_type, event.entity_id)}
                      {event.patient_id !== null && (
                        <Link to={`/patients/${event.patient_id}`} className="block text-xs underline">
                          Ver paciente
                        </Link>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-gray-600">{fieldsLabel(event.fields) || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {query.hasNextPage && (
          <div className="mt-4">
            <Button variant="secondary" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
              {query.isFetchingNextPage ? "Cargando..." : "Cargar más"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
