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

def calcular_horas_en_horario(fecha_inicio, fecha_fin, hora_inicio, hora_fin, dias_operacion):
    inicio = pd.to_datetime(fecha_inicio)
    fin = pd.to_datetime(fecha_fin)

    hora_inicio = time.fromisoformat(hora_inicio)
    hora_fin = time.fromisoformat(hora_fin)

    dias_map = {
        "Lunes": 0,
        "Martes": 1,
        "Miércoles": 2,
        "Jueves": 3,
        "Viernes": 4,
        "Sábado": 5,
        "Domingo": 6
    }

    dias_validos = [dias_map[dia] for dia in dias_operacion.split(",")]

    horas = 0
    fecha_actual = inicio.normalize()

    while fecha_actual <= fin.normalize():
        if fecha_actual.weekday() in dias_validos:
            inicio_operacion = pd.Timestamp.combine(fecha_actual.date(), hora_inicio)
            fin_operacion = pd.Timestamp.combine(fecha_actual.date(), hora_fin)

            inicio_real = max(inicio, inicio_operacion)
            fin_real = min(fin, fin_operacion)

            if fin_real > inicio_real:
                horas += (fin_real - inicio_real).total_seconds() / 3600

        fecha_actual += pd.Timedelta(days=1)

    return horas

def calcular_indicadores(activos, ordenes, paros, repuestos, fecha_inicio, fecha_fin):
    ordenes_f = filtrar_por_fecha(ordenes, "fecha_inicio", fecha_inicio, fecha_fin)
    paros_f = filtrar_por_fecha(paros, "fecha_inicio", fecha_inicio, fecha_fin)

    fecha_inicio_analisis = pd.to_datetime(fecha_inicio)
    fecha_fin_analisis = pd.to_datetime(fecha_fin)

    resultados = []

    for _, activo in activos.iterrows():
        activo_id = activo["id"]

        fecha_registro_activo = pd.to_datetime(activo["fecha_registro"])

        fecha_inicio_real = max(fecha_inicio_analisis, fecha_registro_activo)
        fecha_fin_real = fecha_fin_analisis

        if fecha_inicio_real > fecha_fin_real:
            resultados.append({
                "Código": activo["codigo"],
                "Equipo": activo["nombre"],
                "Área": activo["area"],
                "Tipo": activo["tipo_equipo"],
                "Horas operativas": 0,
                "Total de fallas": 0,
                "Horas de paro": 0,
                "MTBF [h/falla]": "No aplica",
                "MTTR [h/falla]": "No aplica",
                "Disponibilidad operacional [%]": "No aplica",
                "Frecuencia de fallos [fallas/h]": "No calculable",
                "Costo de mantenimiento por equipo": 0
            })
            continue

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
        
        horas_paro = 0
        if not paros_equipo.empty:
            for _, paro in paros_equipo.iterrows():
                horas_paro += calcular_horas_en_horario(
                    paro["fecha_inicio"],
                    paro["fecha_fin"],
                    activo["hora_inicio_operacion"],
                    activo["hora_fin_operacion"],
                    activo["dias_operacion"]
        )

        paros_no_programados = (
            paros_equipo[paros_equipo["tipo_paro"] == "No programado"]
            if not paros_equipo.empty
            else pd.DataFrame()
        )

        horas_paro_no_programado = 0
        if not paros_no_programados.empty:
            for _, paro in paros_no_programados.iterrows():
                horas_paro_no_programado += calcular_horas_en_horario(
                    paro["fecha_inicio"],
                    paro["fecha_fin"],
                    activo["hora_inicio_operacion"],
                    activo["hora_fin_operacion"],
                    activo["dias_operacion"]
                )

        horas_planificadas = calcular_horas_en_horario(
        fecha_inicio_real,
        fecha_fin_real + pd.Timedelta(days=1),
        activo["hora_inicio_operacion"],
        activo["hora_fin_operacion"],
        activo["dias_operacion"]
    )

        horas_operativas = max(horas_planificadas - horas_paro_no_programado, 0)

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
        df_ind = calcular_indicadores(
            activos,
            ordenes,
            paros,
            repuestos,
            fecha_inicio,
            fecha_fin
        )

        horas_operativas_general = pd.to_numeric(
            df_ind["Horas operativas"],
            errors="coerce"
        ).sum()

        total_fallas_general = pd.to_numeric(
            df_ind["Total de fallas"],
            errors="coerce"
        ).sum()

        horas_paro_general = pd.to_numeric(
            df_ind["Horas de paro"],
            errors="coerce"
        ).sum()

        costo_total_general = pd.to_numeric(
            df_ind["Costo de mantenimiento por equipo"],
            errors="coerce"
        ).sum()

        mttr_por_equipo = pd.to_numeric(
            df_ind["MTTR [h/falla]"],
            errors="coerce"
        )

        fallas_por_equipo = pd.to_numeric(
            df_ind["Total de fallas"],
            errors="coerce"
        )

        tiempo_reparacion_general = (
            mttr_por_equipo * fallas_por_equipo
        ).sum()

        if total_fallas_general > 0:
            mtbf_general = horas_operativas_general / total_fallas_general
            mttr_general = tiempo_reparacion_general / total_fallas_general
            disponibilidad_general = (
                mtbf_general / (mtbf_general + mttr_general)
            ) * 100
        else:
            mtbf_general = None
            mttr_general = None
            disponibilidad_general = None

        col1, col2, col3 = st.columns(3)
        col1.metric("Activos registrados", len(activos))
        col2.metric(
            "MTBF general",
            round(mtbf_general, 2) if mtbf_general is not None else "Sin fallas"
        )
        col3.metric(
            "MTTR general",
            round(mttr_general, 2) if mttr_general is not None else "No aplica"
        )

        col4, col5, col6 = st.columns(3)
        col4.metric(
            "Disponibilidad operacional",
            f"{round(disponibilidad_general, 2)} %" if disponibilidad_general is not None else "No aplica"
        )
        col5.metric("Horas totales de paro", round(horas_paro_general, 2))
        col6.metric("Costo total mantenimiento", round(costo_total_general, 2))

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.subheader("Costos por equipo")
            fig = px.bar(
                df_ind,
                x="Equipo",
                y="Costo de mantenimiento por equipo"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_g2:
            st.subheader("Horas de paro por equipo")
            fig = px.bar(
                df_ind,
                x="Equipo",
                y="Horas de paro"
            )
            st.plotly_chart(fig, use_container_width=True)

        col_g3, col_g4 = st.columns(2)

        with col_g3:
            st.subheader("Fallas por equipo")
            fig = px.bar(
                df_ind,
                x="Equipo",
                y="Total de fallas"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_g4:
            st.subheader("Distribución por tipo de intervención")

            ordenes_f = filtrar_por_fecha(
                ordenes,
                "fecha_inicio",
                fecha_inicio,
                fecha_fin
            )

            if not ordenes_f.empty:
                dist = ordenes_f["tipo_mantenimiento"].value_counts().reset_index()
                dist.columns = ["Tipo", "Cantidad"]

                fig = px.pie(
                    dist,
                    names="Tipo",
                    values="Cantidad"
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay órdenes en el período seleccionado.")

        st.subheader("Distribución de paros programados y no programados")

        paros_f = filtrar_por_fecha(
            paros,
            "fecha_inicio",
            fecha_inicio,
            fecha_fin
        )

        if not paros_f.empty:
            dist_paros = paros_f["tipo_paro"].value_counts().reset_index()
            dist_paros.columns = ["Tipo de paro", "Cantidad"]

            fig = px.pie(
                dist_paros,
                names="Tipo de paro",
                values="Cantidad",
                title="Paros programados vs no programados"
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay paros registrados en el período seleccionado.")

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

        fecha_registro = st.date_input("Fecha de registro del activo")

        hora_inicio_operacion = st.time_input("Hora de inicio de operación")
        hora_fin_operacion = st.time_input("Hora de fin de operación")

        dias_operacion_lista = st.multiselect(
            "Días de operación",
            ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
            default=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        )

        dias_operacion = ",".join(dias_operacion_lista)

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
                            fecha_registro,
                            hora_inicio_operacion,
                            hora_fin_operacion,
                            dias_operacion
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        codigo,
                        nombre,
                        area,
                        tipo_equipo,
                        estado,
                        str(fecha_registro),
                        str(hora_inicio_operacion),
                        str(hora_fin_operacion),
                        dias_operacion
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
            fecha_registro,
            hora_inicio_operacion,
            hora_fin_operacion,
            dias_operacion
        FROM activos
    """, conn)

    activos = activos.rename(columns={
        "id": "ID real",
        "codigo": "Código",
        "nombre": "Nombre",
        "area": "Área",
        "tipo_equipo": "Tipo de equipo",
        "estado": "Estado",
        "fecha_registro": "Fecha de registro",
        "hora_inicio_operacion": "Hora inicio operación",
        "hora_fin_operacion": "Hora fin operación",
        "dias_operacion": "Días de operación"
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
                    cursor.execute(
                        "DELETE FROM activos WHERE id = ?",
                        (id_activo,)
                    )

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

    activos = pd.read_sql_query("""
        SELECT 
            id,
            codigo,
            nombre,
            fecha_registro,
            hora_inicio_operacion,
            hora_fin_operacion,
            dias_operacion
        FROM activos
    """, conn)

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
                fecha_registro_activo = pd.to_datetime(
                    activos.loc[activos["Equipo"] == equipo, "fecha_registro"].iloc[0]
                )

                if fecha_fin <= fecha_inicio:
                    st.error("La fecha final debe ser posterior a la fecha inicial.")
                elif fecha_inicio < fecha_registro_activo:
                    st.error("No se puede registrar una orden antes de la fecha de registro del activo.")
                else:
                    hora_inicio_operacion = activos.loc[activos["Equipo"] == equipo, "hora_inicio_operacion"].iloc[0]
                    hora_fin_operacion = activos.loc[activos["Equipo"] == equipo, "hora_fin_operacion"].iloc[0]
                    dias_operacion = activos.loc[activos["Equipo"] == equipo, "dias_operacion"].iloc[0]

                    tiempo_intervencion = calcular_horas_en_horario(
                        fecha_inicio,
                        fecha_fin,
                        hora_inicio_operacion,
                        hora_fin_operacion,
                        dias_operacion
                    )
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

        seleccion_ordenes = st.dataframe(
            tabla_ordenes,
            use_container_width=True,
            selection_mode="multi-row",
            on_select="rerun"
        )

        st.subheader("Eliminar órdenes registradas")

        if seleccion_ordenes.selection.rows:
            ids_ordenes = [
                int(ordenes.iloc[fila]["ID real"])
                for fila in seleccion_ordenes.selection.rows
            ]

            if st.button("Eliminar órdenes seleccionadas"):
                cursor = conn.cursor()

                for id_orden in ids_ordenes:
                    cursor.execute("DELETE FROM repuestos WHERE orden_id = ?", (id_orden,))
                    cursor.execute("DELETE FROM ordenes_trabajo WHERE id = ?", (id_orden,))

                conn.commit()
                st.success("Órdenes seleccionadas eliminadas correctamente.")
                st.rerun()
        else:
            st.info("Seleccione una o varias órdenes para eliminarlas.")

    else:
        st.info("No hay órdenes registradas.")


elif menu == "Paros de equipo":
    st.header("Paros de equipo")

    activos = pd.read_sql_query("""
        SELECT 
            id,
            codigo,
            nombre,
            fecha_registro,
            hora_inicio_operacion,
            hora_fin_operacion,
            dias_operacion
        FROM activos
    """, conn)

    if activos.empty:
        st.warning("Primero debes registrar al menos un activo.")
    else:
        activos["Equipo"] = activos["codigo"] + " - " + activos["nombre"]

        with st.form("form_paro", clear_on_submit=True):
            equipo = st.selectbox("Equipo afectado", activos["Equipo"])
            activo_id = int(activos.loc[activos["Equipo"] == equipo, "id"].iloc[0])

            fecha_inicio = seleccionar_fecha_hora("Inicio del paro")
            fecha_fin = seleccionar_fecha_hora("Fin del paro")
            tipo_paro = st.selectbox(
                "Tipo de paro",
                ["Programado", "No programado"]
            )
            causa = st.text_area("Causa del paro")
            
            guardar = st.form_submit_button("Guardar paro")

            if guardar:
                fecha_registro_activo = pd.to_datetime(
                    activos.loc[activos["Equipo"] == equipo, "fecha_registro"].iloc[0]
                )

                if fecha_fin <= fecha_inicio:
                    st.error("La fecha final debe ser posterior a la fecha inicial.")
                elif fecha_inicio < fecha_registro_activo:
                    st.error("No se puede registrar un paro antes de la fecha de registro del activo.")
                else:
                    hora_inicio_operacion = activos.loc[activos["Equipo"] == equipo, "hora_inicio_operacion"].iloc[0]
                    hora_fin_operacion = activos.loc[activos["Equipo"] == equipo, "hora_fin_operacion"].iloc[0]
                    dias_operacion = activos.loc[activos["Equipo"] == equipo, "dias_operacion"].iloc[0]

                    tiempo_paro = calcular_horas_en_horario(
                        fecha_inicio,
                        fecha_fin,
                        hora_inicio_operacion,
                        hora_fin_operacion,
                        dias_operacion
                    )
                    codigo_equipo = activos.loc[activos["Equipo"] == equipo, "codigo"].iloc[0]
                    nombre_equipo = activos.loc[activos["Equipo"] == equipo, "nombre"].iloc[0]
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO paros
                        (
                            activo_id,
                            codigo_equipo,
                            nombre_equipo,
                            fecha_inicio,
                            fecha_fin,
                            tiempo_paro,
                            tipo_paro,
                            causa
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        activo_id,
                        codigo_equipo,
                        nombre_equipo,
                        str(fecha_inicio),
                        str(fecha_fin),
                        tiempo_paro,
                        tipo_paro,
                        causa
                    ))

                    conn.commit()
                    st.success("Paro registrado correctamente.")
                    st.rerun()

    st.subheader("Paros registrados")

    paros = pd.read_sql_query("""
        SELECT 
            id,
            codigo_equipo AS codigo,
            nombre_equipo AS nombre,
            fecha_inicio,
            fecha_fin,
            tiempo_paro,
            tipo_paro,
            causa
        FROM paros
        ORDER BY fecha_inicio DESC
    """, conn)

    if not paros.empty:
        paros = paros.rename(columns={
            "id": "ID real",
            "codigo": "Código",
            "nombre": "Equipo",
            "fecha_inicio": "Inicio del paro",
            "fecha_fin": "Fin del paro",
            "tiempo_paro": "Tiempo de paro [h]",
            "tipo_paro": "Tipo de paro",
            "causa": "Causa"
        })

        seleccion_paros = st.dataframe(
            paros.drop(columns=["ID real"]),
            use_container_width=True,
            selection_mode="multi-row",
            on_select="rerun"
        )

        st.subheader("Eliminar paros registrados")

        if seleccion_paros.selection.rows:
            ids_paros = [
                int(paros.iloc[fila]["ID real"])
                for fila in seleccion_paros.selection.rows
            ]

            if st.button("Eliminar paros seleccionados"):
                cursor = conn.cursor()

                for id_paro in ids_paros:
                    cursor.execute("DELETE FROM paros WHERE id = ?", (id_paro,))

                conn.commit()
                st.success("Paros seleccionados eliminados correctamente.")
                st.rerun()
        else:
            st.info("Seleccione uno o varios paros para eliminarlos.")
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
            ot.codigo_equipo AS codigo_equipo,
            ot.nombre_equipo AS equipo
        FROM repuestos r
        JOIN ordenes_trabajo ot ON r.orden_id = ot.id
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

        tabla_repuestos = repuestos.drop(columns=["ID real", "Orden de trabajo"]).copy()
        tabla_repuestos = tabla_repuestos[
            [
                "Código equipo",
                "Equipo",
                "Código del repuesto",
                "Descripción",
                "Cantidad utilizada",
                "Costo unitario",
                "Costo total por intervención",
                "Moneda"
            ]
        ]

        seleccion_repuestos = st.dataframe(
            tabla_repuestos,
            use_container_width=True,
            selection_mode="multi-row",
            on_select="rerun"
        )

        st.subheader("Eliminar repuestos registrados")

        if seleccion_repuestos.selection.rows:
            ids_repuestos = [
                int(repuestos.iloc[fila]["ID real"])
                for fila in seleccion_repuestos.selection.rows
            ]

            if st.button("Eliminar repuestos seleccionados"):
                cursor = conn.cursor()

                for id_repuesto in ids_repuestos:
                    cursor.execute("DELETE FROM repuestos WHERE id = ?", (id_repuesto,))

                conn.commit()
                st.success("Repuestos seleccionados eliminados correctamente.")
                st.rerun()
        else:
            st.info("Seleccione uno o varios repuestos para eliminarlos.")
    else:
        st.info("No hay repuestos registrados.")


elif menu == "Base de datos":
    st.header("Base de datos y consultas históricas")

    fecha_inicio, fecha_fin = rango_fechas("Fecha de inicio y fin de análisis")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Activos registrados",
        "Órdenes de trabajo",
        "Paros de equipo",
        "Repuestos usados"
    ])

    with tab1:
        st.subheader("Activos registrados")

        activos_bd = pd.read_sql_query("""
            SELECT
                codigo,
                nombre,
                area,
                tipo_equipo,
                estado,
                fecha_registro,
                hora_inicio_operacion,
                hora_fin_operacion,
                dias_operacion
            FROM activos
        """, conn)

        if activos_bd.empty:
            st.info("No hay activos registrados.")
        else:
            equipos = ["Todos"] + (
                activos_bd["codigo"] + " - " + activos_bd["nombre"]
            ).tolist()

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                equipo_filtro = st.selectbox(
                    "Filtrar por equipo",
                    equipos,
                    key="filtro_equipo_activos"
                )

            with col_f2:
                estado_filtro = st.selectbox(
                    "Filtrar por estado",
                    ["Todos", "Activo", "Fuera de servicio"],
                    key="filtro_estado_activos"
                )

            activos_f = activos_bd.copy()

            activos_f["fecha_registro"] = pd.to_datetime(activos_f["fecha_registro"])

            fecha_inicio_filtro = pd.to_datetime(fecha_inicio)
            fecha_fin_filtro = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)

            activos_f = activos_f[
                (activos_f["fecha_registro"] >= fecha_inicio_filtro) &
                (activos_f["fecha_registro"] < fecha_fin_filtro)
            ]

            if equipo_filtro != "Todos":
                codigo_equipo = equipo_filtro.split(" - ")[0]
                activos_f = activos_f[activos_f["codigo"] == codigo_equipo]

            if estado_filtro != "Todos":
                activos_f = activos_f[activos_f["estado"] == estado_filtro]

            activos_f = activos_f.rename(columns={
                "codigo": "Código",
                "nombre": "Equipo",
                "area": "Área",
                "tipo_equipo": "Tipo de equipo",
                "estado": "Estado",
                "fecha_registro": "Fecha de registro",
                "hora_inicio_operacion": "Hora inicio operación",
                "hora_fin_operacion": "Hora fin operación",
                "dias_operacion": "Días de operación"
            })

            activos_f["Estado"] = activos_f["Estado"].apply(estado_visual)

            if activos_f.empty:
                st.info("No hay activos para los filtros seleccionados.")
            else:
                st.dataframe(activos_f, use_container_width=True)

    with tab2:
        st.subheader("Historial de órdenes de trabajo")

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

        if ordenes.empty:
            st.info("No hay órdenes de trabajo registradas.")
        else:
            equipos_unicos = ordenes[["codigo", "nombre"]].drop_duplicates()
            equipos = ["Todos"] + (
                equipos_unicos["codigo"] + " - " + equipos_unicos["nombre"]
            ).tolist()

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                equipo_filtro = st.selectbox(
                    "Filtrar órdenes por equipo",
                    equipos,
                    key="filtro_equipo_ordenes"
                )

            with col_f2:
                tipo_filtro = st.selectbox(
                    "Filtrar por tipo de mantenimiento",
                    ["Todos", "Correctivo", "Preventivo", "Predictivo"],
                    key="filtro_tipo_ordenes"
                )

            ordenes_f = ordenes.copy()
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

            if ordenes_f.empty:
                st.info("No hay órdenes para los filtros seleccionados.")
            else:
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

                ordenes_f["Costo total"] = (
                    ordenes_f["Costo mano de obra"] +
                    ordenes_f["Otros costos"]
                )

                seleccion_historial = st.dataframe(
                    ordenes_f,
                    use_container_width=True,
                    selection_mode="multi-row",
                    on_select="rerun"
                )

                st.subheader("Eliminar órdenes del historial")

                if seleccion_historial.selection.rows:
                    ids_ordenes = [
                        int(ordenes_f.iloc[fila]["ID"])
                        for fila in seleccion_historial.selection.rows
                    ]

                    if st.button("Eliminar órdenes seleccionadas", key="btn_eliminar_ordenes_bd"):
                        cursor = conn.cursor()

                        for id_orden in ids_ordenes:
                            cursor.execute("DELETE FROM repuestos WHERE orden_id = ?", (id_orden,))
                            cursor.execute("DELETE FROM ordenes_trabajo WHERE id = ?", (id_orden,))

                        conn.commit()
                        st.success("Órdenes seleccionadas eliminadas del historial.")
                        st.rerun()
                else:
                    st.info("Seleccione una o varias órdenes para eliminarlas.")

    with tab3:
        st.subheader("Historial de paros de equipo")

        paros = pd.read_sql_query("""
            SELECT 
                id,
                codigo_equipo AS codigo,
                nombre_equipo AS nombre,
                fecha_inicio,
                fecha_fin,
                tiempo_paro,
                tipo_paro,
                causa
            FROM paros
        """, conn)

        if paros.empty:
            st.info("No hay paros registrados.")
        else:
            equipos_unicos = paros[["codigo", "nombre"]].drop_duplicates()
            equipos = ["Todos"] + (
                equipos_unicos["codigo"] + " - " + equipos_unicos["nombre"]
            ).tolist()

            col_f1, col_f2 = st.columns(2)

            with col_f1:
                equipo_filtro = st.selectbox(
                    "Filtrar paros por equipo",
                    equipos,
                    key="filtro_equipo_paros"
                )

            with col_f2:
                tipo_paro_filtro = st.selectbox(
                    "Filtrar por tipo de paro",
                    ["Todos", "Programado", "No programado"],
                    key="filtro_tipo_paro"
                )

            paros_f = paros.copy()
            paros_f["fecha_inicio"] = pd.to_datetime(paros_f["fecha_inicio"])
            paros_f["fecha_fin"] = pd.to_datetime(paros_f["fecha_fin"])

            fecha_inicio_filtro = pd.to_datetime(fecha_inicio)
            fecha_fin_filtro = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)

            paros_f = paros_f[
                (paros_f["fecha_inicio"] >= fecha_inicio_filtro) &
                (paros_f["fecha_fin"] < fecha_fin_filtro)
            ]

            if equipo_filtro != "Todos":
                codigo_equipo = equipo_filtro.split(" - ")[0]
                paros_f = paros_f[paros_f["codigo"] == codigo_equipo]

            if tipo_paro_filtro != "Todos":
                paros_f = paros_f[paros_f["tipo_paro"] == tipo_paro_filtro]

            if paros_f.empty:
                st.info("No hay paros para los filtros seleccionados.")
            else:
                paros_f = paros_f.rename(columns={
                    "id": "ID",
                    "codigo": "Código",
                    "nombre": "Equipo",
                    "fecha_inicio": "Fecha de inicio",
                    "fecha_fin": "Fecha de fin",
                    "tiempo_paro": "Tiempo de paro [h]",
                    "tipo_paro": "Tipo de paro",
                    "causa": "Causa"
                })

                seleccion_paros_bd = st.dataframe(
                    paros_f,
                    use_container_width=True,
                    selection_mode="multi-row",
                    on_select="rerun"
                )

                st.subheader("Eliminar paros del historial")

                if seleccion_paros_bd.selection.rows:
                    ids_paros = [
                        int(paros_f.iloc[fila]["ID"])
                        for fila in seleccion_paros_bd.selection.rows
                    ]

                    if st.button("Eliminar paros seleccionados", key="btn_eliminar_paros_bd"):
                        cursor = conn.cursor()

                        for id_paro in ids_paros:
                            cursor.execute("DELETE FROM paros WHERE id = ?", (id_paro,))

                        conn.commit()
                        st.success("Paros seleccionados eliminados del historial.")
                        st.rerun()
                else:
                    st.info("Seleccione uno o varios paros para eliminarlos.")

    with tab4:
        st.subheader("Historial de repuestos usados")

        repuestos = pd.read_sql_query("""
            SELECT
                r.id,
                r.codigo,
                ot.nombre_equipo AS equipo,
                r.descripcion,
                r.cantidad_utilizada,
                r.costo_unitario,
                r.costo_total,
                r.moneda,
                ot.id AS orden_id,
                ot.codigo_equipo AS codigo_equipo,
                ot.fecha_inicio AS fecha_inicio,
                ot.fecha_fin AS fecha_fin
            FROM repuestos r
            JOIN ordenes_trabajo ot ON r.orden_id = ot.id
        """, conn)

        if repuestos.empty:
            st.info("No hay repuestos registrados.")
        else:
            equipos_unicos = repuestos[["codigo_equipo", "equipo"]].drop_duplicates()
            equipos = ["Todos"] + (
                equipos_unicos["codigo_equipo"] + " - " + equipos_unicos["equipo"]
            ).tolist()

            equipo_filtro = st.selectbox(
                "Filtrar repuestos por equipo",
                equipos,
                key="filtro_equipo_repuestos"
            )

            repuestos_f = repuestos.copy()
            repuestos_f["fecha_inicio"] = pd.to_datetime(repuestos_f["fecha_inicio"])
            repuestos_f["fecha_fin"] = pd.to_datetime(repuestos_f["fecha_fin"])

            fecha_inicio_filtro = pd.to_datetime(fecha_inicio)
            fecha_fin_filtro = pd.to_datetime(fecha_fin) + pd.Timedelta(days=1)

            repuestos_f = repuestos_f[
                (repuestos_f["fecha_inicio"] >= fecha_inicio_filtro) &
                (repuestos_f["fecha_fin"] < fecha_fin_filtro)
            ]

            if equipo_filtro != "Todos":
                codigo_equipo = equipo_filtro.split(" - ")[0]
                repuestos_f = repuestos_f[repuestos_f["codigo_equipo"] == codigo_equipo]

            if repuestos_f.empty:
                st.info("No hay repuestos para los filtros seleccionados.")
            else:
                repuestos_f = repuestos_f.rename(columns={
                    "id": "ID",
                    "codigo": "Código del repuesto",
                    "equipo": "Equipo",
                    "descripcion": "Descripción",
                    "cantidad_utilizada": "Cantidad utilizada",
                    "costo_unitario": "Costo unitario",
                    "costo_total": "Costo total",
                    "moneda": "Moneda",
                    "orden_id": "Orden de trabajo",
                    "codigo_equipo": "Código equipo",
                    "fecha_inicio": "Fecha de inicio",
                    "fecha_fin": "Fecha de fin"
                })

                repuestos_f = repuestos_f[
                    [
                        "ID",
                        "Código equipo",
                        "Equipo",
                        "Código del repuesto",
                        "Descripción",
                        "Cantidad utilizada",
                        "Costo unitario",
                        "Costo total",
                        "Moneda",
                        "Fecha de inicio",
                        "Fecha de fin"
                    ]
                ]

                seleccion_repuestos_bd = st.dataframe(
                    repuestos_f,
                    use_container_width=True,
                    selection_mode="multi-row",
                    on_select="rerun"
                )

                st.subheader("Eliminar repuestos del historial")

                if seleccion_repuestos_bd.selection.rows:
                    ids_repuestos = [
                        int(repuestos_f.iloc[fila]["ID"])
                        for fila in seleccion_repuestos_bd.selection.rows
                    ]

                    if st.button("Eliminar repuestos seleccionados", key="btn_eliminar_repuestos_bd"):
                        cursor = conn.cursor()

                        for id_repuesto in ids_repuestos:
                            cursor.execute("DELETE FROM repuestos WHERE id = ?", (id_repuesto,))

                        conn.commit()
                        st.success("Repuestos seleccionados eliminados del historial.")
                        st.rerun()
                else:
                    st.info("Seleccione uno o varios repuestos para eliminarlos.")

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
