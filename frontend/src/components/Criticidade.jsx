export default function Criticidade({ valor }) {
  const bloqueante = valor === "bloqueante";
  return (
    <span className={`marca ${bloqueante ? "marca-bloqueante" : "marca-aviso"}`}>
      {bloqueante ? "Bloqueante" : "Aviso"}
    </span>
  );
}
