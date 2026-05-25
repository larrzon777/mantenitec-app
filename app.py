from datetime import datetime, time, timedelta
import streamlit as st
import pandas as pd
import plotly.express as px
from database import create_tables, get_connection

st.set_page_config(
    page_title="ManteniTEC",
    page_icon="🔧",
    layout="wide"
)

create_tables()
conn = get_connection()

st.title("🔧 ManteniTEC")
st.subheader("Aplicación para Gestión de Mantenimiento e Indicadores")

menu = st.sidebar.radio(
    "Menú principal",
    [
        "Dashboard",
        "Registro de activos",
        "Órdenes de trabajo",
        "Paros de equipo",
        "Repuestos usados",
        "Base de datos",
        "Indicadores"
    ]
)

def seleccionar_fecha_hora(titulo):
    st.write(titulo)

    col1, col2, col3 = st.columns(3)

    with col1:
        fecha = st.date_input(f"Fecha - {titulo}")

    with col2:
        hora = st.number_input(
            f"Hora - {titulo}",
            min_value=0,
            max_value=23,
            value=8,
            step=1
        )

    with col3:
        minuto = st.number_input(
            f"Minuto - {titulo}",
            min_value=0,
            max_value=59,
            value=0,
            step=1
        )

    return datetime.combine(fecha, time(int(hora), int(minuto)))

def filtrar_por_fecha(df, columna_fecha, fecha_inicio, fecha_fin):
    if df.empty:
        return df

    df = df.copy()
    df[columna_fecha] = pd.to_datetime(df[columna_fecha])
    inicio = pd.to_datetime(fecha_inicio)
    fin = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)

    return df[(df[columna_fecha] >= inicio) & (df[columna_fecha] < fin)]


def rango_fechas(titulo="Período de análisis"):
    st.subheader(titulo)

    with st.form(f"form_{titulo}"):
        col1, col2 = st.columns(2)

        with col1:
            fecha_inicio = st.date_input("Fecha de inicio")

        with col2:
            fecha_fin = st.date_input("Fecha de fin")

        st.form_submit_button("Listo")

    return fecha_inicio, fecha_fin


def estado_visual(estado):
    if estado == "Activo":
        return "🟢 Activo"
    return "🟠 Fuera de servicio"


def calcular_indicadores(activos, ordenes, paros, repuestos, fecha_inicio, fecha_fin):
    ordenes_f = filtrar_por_fecha(ordenes, "fecha_inicio", fecha_inicio, fecha_fin)
    paros_f = filtrar_por_fecha(paros, "fecha_inicio", fecha_inicio, fecha_fin)

    dias_periodo = (pd.to_datetime(fecha_fin) - pd.to_datetime(fecha_inicio)).days + 1
    semanas_periodo = dias_periodo / 7

    resultados = []

    for _, activo in activos.iterrows():
        activo_id = activo["id"]

        ordenes_equipo = (
            ordenes_f[ordenes_f["activo_id"] == activo_id]
            if not ordenes_f.empty else pd.DataFrame()
        )

        paros_equipo = (
            paros_f[paros_f["activo_id"] == activo_id]
            if not paros_f.empty else pd.DataFrame()
        )

        fallas = (
            ordenes_equipo[
                (ordenes_equipo["tipo_mantenimiento"] == "Correctivo") &
                (ordenes_equipo["es_falla"] == 1)
            ]
            if not ordenes_equipo.empty else pd.DataFrame()
        )

        total_fallas = len(fallas)
        tiempo_total_reparacion = fallas["tiempo_intervencion"].sum() if not fallas.empty else 0
        horas_paro = paros_equipo["tiempo_paro"].sum() if not paros_equipo.empty else 0

        horas_planificadas = (
            activo["horas_uso_dia"] *
            activo["dias_operacion_semana"] *
            semanas_periodo
        )

        horas_operativas = max(horas_planificadas - horas_paro, 0)

        mtbf = horas_operativas / total_fallas if total_fallas > 0 else None
        mttr = tiempo_total_reparacion / total_fallas if total_fallas > 0 else None

        if mtbf is not None and mttr is not None:
            disponibilidad = (mtbf / (mtbf + mttr)) * 100
        else:
            disponibilidad = None

        frecuencia = total_fallas / horas_operativas if horas_operativas > 0 else None

        costo_mano_obra = ordenes_equipo["costo_mano_obra"].sum() if not ordenes_equipo.empty else 0
        otros_costos = ordenes_equipo["otros_costos"].sum() if not ordenes_equipo.empty else 0

        costo_repuestos = 0
        if not repuestos.empty and not ordenes_equipo.empty:
            ids_ordenes = ordenes_equipo["id"].tolist()
            costo_repuestos = repuestos[
                repuestos["orden_id"].isin(ids_ordenes)
            ]["costo_total"].sum()

        costo_total = costo_mano_obra + otros_costos + costo_repuestos

        resultados.append({
            "Código": activo["codigo"],
            "Equipo": activo["nombre"],
            "Área": activo["area"],
            "Tipo": activo["tipo_equipo"],
            "Horas operativas": round(horas_operativas, 2),
            "Total de fallas": total_fallas,
            "Horas de paro": round(horas_paro, 2),
            "MTBF [h/falla]": round(mtbf, 2) if mtbf is not None else "Sin fallas",
            "MTTR [h/falla]": round(mttr, 2) if mttr is not None else "No aplica",
            "Disponibilidad operacional [%]": round(disponibilidad, 2) if disponibilidad is not None else "No aplica",
            "Frecuencia de fallos [fallas/h]": round(frecuencia, 6) if frecuencia is not None else "No calculable",
            "Costo de mantenimiento por equipo": round(costo_total, 2)
        })

    return pd.DataFrame(resultados)


if menu == "Dashboard":
    st.header("Dashboard general")

    fecha_inicio, fecha_fin = rango_fechas()

    activos = pd.read_sql_query("SELECT * FROM activos", conn)
    ordenes = pd.read_sql_query("SELECT * FROM ordenes_trabajo", conn)
    paros = pd.read_sql_query("SELECT * FROM paros", conn)
    repuestos = pd.read_sql_query("SELECT * FROM repuestos", conn)

    if activos.empty:
        st.warning("No hay activos registrados.")
    else:
        df_ind = calcular_indicadores(activos, ordenes, paros, repuestos, fecha_inicio, fecha_fin)

        mtbf_prom = pd.to_numeric(df_ind["MTBF [h/falla]"], errors="coerce").mean()
        mttr_prom = pd.to_numeric(df_ind["MTTR [h/falla]"], errors="coerce").mean()
        disp_prom = pd.to_numeric(df_ind["Disponibilidad operacional [%]"], errors="coerce").mean()

        col1, col2, col3 = st.columns(3)
        col1.metric("Activos registrados", len(activos))
        col2.metric("MTBF general", round(mtbf_prom, 2) if pd.notna(mtbf_prom) else "Sin datos")
        col3.metric("MTTR general", round(mttr_prom, 2) if pd.notna(mttr_prom) else "Sin datos")

        col4, col5, col6 = st.columns(3)
        col4.metric("Disponibilidad operacional", f"{round(disp_prom, 2)} %" if pd.notna(disp_prom) else "Sin datos")
        col5.metric("Horas totales de paro", round(df_ind["Horas de paro"].sum(), 2))
        col6.metric("Costo total mantenimiento", round(df_ind["Costo de mantenimiento por equipo"].sum(), 2))

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("Costos por equipo")
            fig = px.bar(df_ind, x="Equipo", y="Costo de mantenimiento por equipo")
            st.plotly_chart(fig, use_container_width=True)

        with col_g2:
            st.subheader("Horas de paro por equipo")
            fig = px.bar(df_ind, x="Equipo", y="Horas de paro")
            st.plotly_chart(fig, use_container_width=True)

        col_g3, col_g4 = st.columns(2)

        with col_g3:
            st.subheader("Fallas por equipo")
            fig = px.bar(df_ind, x="Equipo", y="Total de fallas")
            st.plotly_chart(fig, use_container_width=True)

        with col_g4:
            st.subheader("Distribución por tipo de intervención")
            ordenes_f = filtrar_por_fecha(ordenes, "fecha_inicio", fecha_inicio, fecha_fin)

            if not ordenes_f.empty:
                dist = ordenes_f["tipo_mantenimiento"].value_counts().reset_index()
                dist.columns = ["Tipo", "Cantidad"]
                fig = px.pie(dist, names="Tipo", values="Cantidad")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay órdenes en el período seleccionado.")


elif menu == "Registro de activos":
    st.header("Registro de activos")

    with st.form("form_activo", clear_on_submit=True):
        codigo = st.text_input("Código del equipo")
        nombre = st.text_input("Nombre del equipo")
        area = st.text_input("Área o proceso")

        tipo_equipo = st.selectbox(
            "Tipo de equipo",
            ["Motor", "Bomba", "Compresor", "Ventilador", "Transportador", "Otro"]
        )

        estado = st.selectbox("Estado operativo", ["Activo", "Fuera de servicio"])

        horas_uso_dia = st.number_input(
            "Horas de uso por día",
            min_value=0.0,
            max_value=24.0,
            value=8.0
        )

        dias_operacion_semana = st.number_input(
            "Días de operación por semana",
            min_value=0.0,
            max_value=7.0,
            value=5.0
        )

        guardar = st.form_submit_button("Guardar activo")

        if guardar:
            if codigo == "" or nombre == "" or area == "":
                st.error("Debe completar código, nombre y área.")
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO activos 
                        (
                            codigo,
                            nombre,
                            area,
                            tipo_equipo,
                            estado,
                            horas_uso_dia,
                            dias_operacion_semana
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        codigo,
                        nombre,
                        area,
                        tipo_equipo,
                        estado,
                        horas_uso_dia,
                        dias_operacion_semana
                    ))
                    conn.commit()
                    st.success("Activo guardado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    st.subheader("Activos registrados")

    activos = pd.read_sql_query("""
        SELECT
            id,
            codigo,
            nombre,
            area,
            tipo_equipo,
            estado,
            horas_uso_dia,
            dias_operacion_semana
        FROM activos
    """, conn)

    activos = activos.rename(columns={
        "id": "ID real",
        "codigo": "Código",
        "nombre": "Nombre",
        "area": "Área",
        "tipo_equipo": "Tipo de equipo",
        "estado": "Estado",
        "horas_uso_dia": "Horas de uso por día",
        "dias_operacion_semana": "Días de operación por semana"
    })

    activos["Estado"] = activos["Estado"].apply(estado_visual)
    activos_mostrar = activos.drop(columns=["ID real"])

    seleccion = st.dataframe(
        activos_mostrar,
        use_container_width=True,
        selection_mode="multi-row",
        on_select="rerun"
    )

    st.subheader("Cambiar estado de activos")

    if activos.empty:
        st.info("No hay activos registrados.")
    else:
        if seleccion.selection.rows:
            ids_seleccionados = [
                int(activos.iloc[fila]["ID real"])
                for fila in seleccion.selection.rows
            ]

            if st.button("Eliminar activos seleccionados"):
                cursor = conn.cursor()

                for id_activo in ids_seleccionados:
                    cursor.execute("DELETE FROM activos WHERE id = ?", (id_activo,))

                conn.commit()
                st.success("Activos eliminados del catálogo. El historial se conserva en Base de datos.")
                st.rerun()

        if st.button("Eliminar TODOS los activos"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activos")
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='activos'")
            conn.commit()
            st.warning("Todos los activos fueron eliminados del catálogo. El historial se conserva en Base de datos.")
            st.rerun()


elif menu == "Órdenes de trabajo":
    st.header("Órdenes de trabajo")

    activos = pd.read_sql_query("SELECT id, codigo, nombre FROM activos", conn)

    if activos.empty:
        st.warning("Primero debes registrar al menos un activo.")
    else:
        activos["Equipo"] = activos["codigo"] + " - " + activos["nombre"]

        with st.form("form_orden", clear_on_submit=True):
            equipo = st.selectbox("Equipo asociado", activos["Equipo"])
            activo_id = int(activos.loc[activos["Equipo"] == equipo, "id"].iloc[0])

            tipo_mantenimiento = st.selectbox(
                "Tipo de mantenimiento",
                ["Correctivo", "Preventivo", "Predictivo"]
            )

            fecha_inicio = seleccionar_fecha_hora("Inicio de la OT")
            fecha_fin = seleccionar_fecha_hora("Finalización de la OT")

            descripcion = st.text_area("Descripción de la falla o actividad realizada")
            personal = st.text_input("Personal involucrado")

            moneda = st.selectbox("Moneda", ["CRC", "USD"])

            costo_mano_obra = st.number_input("Costo de mano de obra", min_value=0.0, value=0.0)
            otros_costos = st.number_input("Otros costos", min_value=0.0, value=0.0)

            guardar = st.form_submit_button("Guardar orden de trabajo")

            if guardar:
                if fecha_fin <= fecha_inicio:
                    st.error("La fecha final debe ser posterior a la fecha inicial.")
                else:
                    tiempo_intervencion = (fecha_fin - fecha_inicio).total_seconds() / 3600
                    es_falla = 1 if tipo_mantenimiento == "Correctivo" else 0

                    codigo_equipo = activos.loc[activos["Equipo"] == equipo, "codigo"].iloc[0]
                    nombre_equipo = activos.loc[activos["Equipo"] == equipo, "nombre"].iloc[0]

                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO ordenes_trabajo
                        (
                            activo_id,
                            codigo_equipo,
                            nombre_equipo,
                            tipo_mantenimiento,
                            fecha_inicio,
                            fecha_fin,
                            descripcion,
                            personal,
                            tiempo_intervencion,
                            costo_mano_obra,
                            otros_costos,
                            moneda,
                            es_falla
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        activo_id,
                        codigo_equipo,
                        nombre_equipo,
                        tipo_mantenimiento,
                        str(fecha_inicio),
                        str(fecha_fin),
                        descripcion,
                        personal,
                        tiempo_intervencion,
                        costo_mano_obra,
                        otros_costos,
                        moneda,
                        es_falla
                    ))

                    conn.commit()
                    st.success("Orden de trabajo guardada correctamente.")
                    st.rerun()

    st.subheader("Órdenes registradas")

    ordenes = pd.read_sql_query("""
        SELECT 
            id,
            codigo_equipo AS codigo,
            nombre_equipo AS nombre,
            tipo_mantenimiento,
            fecha_inicio,
            fecha_fin,
            tiempo_intervencion,
            descripcion,
            personal,
            moneda,
            costo_mano_obra,
            otros_costos
        FROM ordenes_trabajo
    """, conn)

    if not ordenes.empty:
        ordenes = ordenes.rename(columns={
            "id": "ID real",
            "codigo": "Código",
            "nombre": "Equipo",
            "tipo_mantenimiento": "Tipo de mantenimiento",
            "fecha_inicio": "Fecha de inicio",
            "fecha_fin": "Fecha de finalización",
            "tiempo_intervencion": "Tiempo de intervención [h]",
            "descripcion": "Descripción",
            "personal": "Personal",
            "moneda": "Moneda",
            "costo_mano_obra": "Costo mano de obra",
            "otros_costos": "Otros costos"
        })

        tabla_ordenes = ordenes.drop(columns=["ID real"]).copy()

        tabla_ordenes["Costo total"] = (
            tabla_ordenes["Costo mano de obra"] +
            tabla_ordenes["Otros costos"]
        )

        st.dataframe(tabla_ordenes, use_container_width=True)

    else:
        st.info("No hay órdenes registradas.")


elif menu == "Paros de equipo":
    st.header("Paros de equipo")

    activos = pd.read_sql_query("SELECT id, codigo, nombre FROM activos", conn)

    if activos.empty:
        st.warning("Primero debes registrar al menos un activo.")
    else:
        activos["Equipo"] = activos["codigo"] + " - " + activos["nombre"]

        with st.form("form_paro", clear_on_submit=True):
            equipo = st.selectbox("Equipo afectado", activos["Equipo"])
            activo_id = int(activos.loc[activos["Equipo"] == equipo, "id"].iloc[0])

            fecha_inicio = seleccionar_fecha_hora("Inicio del paro")
            fecha_fin = seleccionar_fecha_hora("Fin del paro")

            causa = st.text_area("Causa del paro")

            guardar = st.form_submit_button("Guardar paro")

            if guardar:
                if fecha_fin <= fecha_inicio:
                    st.error("La fecha final debe ser posterior a la fecha inicial.")
                else:
                    tiempo_paro = (fecha_fin - fecha_inicio).total_seconds() / 3600
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO paros
                        (activo_id, fecha_inicio, fecha_fin, tiempo_paro, causa)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        activo_id,
                        str(fecha_inicio),
                        str(fecha_fin),
                        tiempo_paro,
                        causa
                    ))

                    conn.commit()
                    st.success("Paro registrado correctamente.")
                    st.rerun()

    st.subheader("Paros registrados")

    paros = pd.read_sql_query("""
        SELECT 
            p.id,
            a.codigo,
            a.nombre,
            p.fecha_inicio,
            p.fecha_fin,
            p.tiempo_paro,
            p.causa
        FROM paros p
        JOIN activos a ON p.activo_id = a.id
        ORDER BY p.fecha_inicio DESC
    """, conn)

    if not paros.empty:
        paros = paros.rename(columns={
            "id": "ID real",
            "codigo": "Código",
            "nombre": "Equipo",
            "fecha_inicio": "Inicio del paro",
            "fecha_fin": "Fin del paro",
            "tiempo_paro": "Tiempo de paro [h]",
            "causa": "Causa"
        })

        st.dataframe(paros.drop(columns=["ID real"]), use_container_width=True)
    else:
        st.info("No hay paros registrados.")


elif menu == "Repuestos usados":
    st.header("Repuestos usados por intervención")

    ordenes = pd.read_sql_query("""
        SELECT 
            ot.id,
            a.codigo,
            a.nombre,
            ot.fecha_inicio
        FROM ordenes_trabajo ot
        JOIN activos a ON ot.activo_id = a.id
        ORDER BY ot.fecha_inicio DESC
    """, conn)

    if ordenes.empty:
        st.warning("Primero debes registrar una orden de trabajo.")
    else:
        ordenes["Orden"] = (
            "OT-" + ordenes["id"].astype(str) +
            " | " + ordenes["codigo"] +
            " - " + ordenes["nombre"]
        )

        with st.form("form_repuesto", clear_on_submit=True):
            orden = st.selectbox("Orden de trabajo asociada", ordenes["Orden"])
            orden_id = int(ordenes.loc[ordenes["Orden"] == orden, "id"].iloc[0])

            codigo = st.text_input("Código del repuesto")
            descripcion = st.text_input("Descripción")

            cantidad = st.number_input(
                "Cantidad utilizada",
                min_value=1,
                value=1,
                step=1
            )

            moneda = st.selectbox("Moneda", ["CRC", "USD"])

            costo_unitario = st.number_input("Costo unitario", min_value=0.0, value=0.0)

            guardar = st.form_submit_button("Guardar repuesto utilizado")

            if guardar:
                if codigo == "" or descripcion == "":
                    st.error("Debe completar código y descripción.")
                else:
                    costo_total = int(cantidad) * costo_unitario

                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO repuestos
                        (
                            orden_id,
                            codigo,
                            descripcion,
                            cantidad_utilizada,
                            costo_unitario,
                            costo_total,
                            moneda
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        orden_id,
                        codigo,
                        descripcion,
                        int(cantidad),
                        costo_unitario,
                        costo_total,
                        moneda
                    ))

                    conn.commit()
                    st.success(f"Repuesto guardado. Costo total: {round(costo_total, 2)} {moneda}")
                    st.rerun()

    st.subheader("Repuestos registrados")

    repuestos = pd.read_sql_query("""
        SELECT
            r.id,
            r.codigo,
            r.descripcion,
            r.cantidad_utilizada,
            r.costo_unitario,
            r.costo_total,
            r.moneda,
            ot.id AS orden_id,
            a.codigo AS codigo_equipo,
            a.nombre AS equipo
        FROM repuestos r
        JOIN ordenes_trabajo ot ON r.orden_id = ot.id
        JOIN activos a ON ot.activo_id = a.id
        ORDER BY r.id DESC
    """, conn)

    if not repuestos.empty:
        repuestos = repuestos.rename(columns={
            "id": "ID real",
            "codigo": "Código del repuesto",
            "descripcion": "Descripción",
            "cantidad_utilizada": "Cantidad utilizada",
            "costo_unitario": "Costo unitario",
            "costo_total": "Costo total por intervención",
            "moneda": "Moneda",
            "orden_id": "Orden de trabajo",
            "codigo_equipo": "Código equipo",
            "equipo": "Equipo"
        })

        st.dataframe(repuestos.drop(columns=["ID real"]), use_container_width=True)
    else:
        st.info("No hay repuestos registrados.")


elif menu == "Base de datos":
    st.header("Base de datos y consultas históricas")

    fecha_inicio, fecha_fin = rango_fechas("Fecha de inicio y fin de análisis")

    activos = pd.read_sql_query("SELECT * FROM activos", conn)

    ordenes = pd.read_sql_query("""
        SELECT 
            ot.id,
            a.codigo,
            a.nombre,
            a.estado,
            ot.tipo_mantenimiento,
            ot.fecha_inicio,
            ot.fecha_fin,
            ot.tiempo_intervencion,
            ot.descripcion,
            ot.personal,
            ot.moneda,
            ot.costo_mano_obra,
            ot.otros_costos
        FROM ordenes_trabajo ot
        JOIN activos a ON ot.activo_id = a.id
    """, conn)

    if activos.empty:
        st.warning("No hay activos registrados.")
    else:
        equipos = ["Todos"] + (activos["codigo"] + " - " + activos["nombre"]).tolist()
        equipo_filtro = st.selectbox("Filtrar por equipo", equipos)

        tipos = ["Todos", "Correctivo", "Preventivo", "Predictivo"]
        tipo_filtro = st.selectbox("Filtrar por tipo de mantenimiento", tipos)

    ordenes_f = ordenes.copy()

    if not ordenes_f.empty:
        ordenes_f["fecha_inicio"] = pd.to_datetime(ordenes_f["fecha_inicio"])
        ordenes_f["fecha_fin"] = pd.to_datetime(ordenes_f["fecha_fin"])

        fecha_inicio_filtro = pd.to_datetime(fecha_inicio)
        fecha_fin_filtro = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)

        ordenes_f = ordenes_f[
            (ordenes_f["fecha_inicio"] >= fecha_inicio_filtro) &
            (ordenes_f["fecha_fin"] < fecha_fin_filtro)
        ]

        if equipo_filtro != "Todos":
            codigo_equipo = equipo_filtro.split(" - ")[0]
            ordenes_f = ordenes_f[ordenes_f["codigo"] == codigo_equipo]

        if tipo_filtro != "Todos":
            ordenes_f = ordenes_f[ordenes_f["tipo_mantenimiento"] == tipo_filtro]

        if not ordenes_f.empty:
            ordenes_f = ordenes_f.rename(columns={
                "id": "ID",
                "codigo": "Código",
                "nombre": "Equipo",
                "tipo_mantenimiento": "Tipo de mantenimiento",
                "fecha_inicio": "Fecha de inicio",
                "fecha_fin": "Fecha de fin",
                "tiempo_intervencion": "Tiempo intervención [h]",
                "descripcion": "Descripción",
                "personal": "Personal",
                "moneda": "Moneda",
                "costo_mano_obra": "Costo mano de obra",
                "otros_costos": "Otros costos"
            })
            tabla_historial = ordenes_f.copy()

            fila_total = {col: "" for col in tabla_historial.columns}
            fila_total["Equipo"] = "TOTAL"
            fila_total["Costo mano de obra"] = tabla_historial["Costo mano de obra"].sum()
            fila_total["Otros costos"] = tabla_historial["Otros costos"].sum()

            tabla_historial = pd.concat(
                [tabla_historial, pd.DataFrame([fila_total])],
                ignore_index=True
            )

            tabla_historial = ordenes_f.copy()

            tabla_historial["Costo total"] = (
                tabla_historial["Costo mano de obra"] +
                tabla_historial["Otros costos"]
            )

            seleccion_historial = st.dataframe(
                tabla_historial,
                use_container_width=True,
                selection_mode="multi-row",
                on_select="rerun"
            )
            st.subheader("Eliminar registros del historial")

            if seleccion_historial.selection.rows:
                ids_ordenes = [
                    int(ordenes_f.iloc[fila]["ID"])
                    for fila in seleccion_historial.selection.rows
                ]

                st.warning(f"Órdenes seleccionadas: {ids_ordenes}")

                if st.button("Eliminar órdenes seleccionadas del historial"):
                    cursor = conn.cursor()

                    for id_orden in ids_ordenes:
                        cursor.execute("DELETE FROM repuestos WHERE orden_id = ?", (id_orden,))
                        cursor.execute("DELETE FROM ordenes_trabajo WHERE id = ?", (id_orden,))

                    conn.commit()
                    st.success("Registros seleccionados eliminados del historial.")
                    st.rerun()
            else:
                st.info("Seleccione una o varias filas del historial para eliminarlas.")

        else:
            st.info("No hay datos para los filtros seleccionados.")


elif menu == "Indicadores":
    st.header("Indicadores obligatorios de mantenimiento")

    fecha_inicio, fecha_fin = rango_fechas()

    activos = pd.read_sql_query("SELECT * FROM activos", conn)
    ordenes = pd.read_sql_query("SELECT * FROM ordenes_trabajo", conn)
    paros = pd.read_sql_query("SELECT * FROM paros", conn)
    repuestos = pd.read_sql_query("SELECT * FROM repuestos", conn)

    if activos.empty:
        st.warning("No hay activos registrados.")
    else:
        df_indicadores = calcular_indicadores(
            activos,
            ordenes,
            paros,
            repuestos,
            fecha_inicio,
            fecha_fin
        )

        st.subheader("Resultados por equipo")
        st.dataframe(df_indicadores, use_container_width=True)
