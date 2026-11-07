const trazos = {
  semana: "M3 5h18v16H3ZM7 2v6m10-6v6M3 10h18m-14 5 3 3 6-6",
  cobros: "M3 5h18v15H3ZM7 2v6m10-6v6M7 12h4m-4 4h7m3-5 2 2-2 2",
  simulador: "M4 3h16v18H4ZM8 7h8M8 11h1m6 0h1M8 15h1m6 0h1M8 18h1m6 0h1",
  faenas: "M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6M8 10h1m6 0h1M11 7h2",
  "seguimiento-pagos": "M3 4h18v17H3ZM7 9l2 2 4-4m-6 9h10",
  inicio: "M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  productividad: "M4 20V10m7 10V4m7 16v-7M2 21h20",
  trabajadores: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m8-7a4 4 0 0 1 0 7.75",
  cosechas: "M12 21v-9M12 16C4 16 3 11 3 5c6 0 9 3 9 7m0 3c0-8 3-11 9-11 0 6-3 11-9 11",
  importacion: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  pagos: "M3 6h18v14H3ZM3 6V3h14v3m0 6h4v4h-4Z",
  reportes: "M14 2H5v20h14V7Zm0 0v5h5M8 12h8m-8 4h6",
  asistente: "M4 3h16v14H8l-4 4Zm4 5h8m-8 4h5",
  "analisis-ia": "M12 3 9 9l-6 3 6 3 3 6 3-6 6-3-6-3Zm7-1v4m-2-2h4",
  administracion: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1Z",
  usuarios: "M8 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8M1 21v-3a5 5 0 0 1 5-5h4m7-3 5 2v4c0 3-5 6-5 6s-5-3-5-6v-4Z",
  cuenta: "M20 21a8 8 0 0 0-16 0M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10",
  salir: "M9 3H3v18h6m5-14 5 5-5 5m-6-5h11",
  flecha: "M5 12h14m-5-5 5 5-5 5",
  menu: "M4 6h16M4 12h16M4 18h16",
  actualizar: "M20 7a9 9 0 1 0 1 9M20 2v6h-6",
};

export default function Icon({ nombre, size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={trazos[nombre] || trazos.inicio} /></svg>;
}
