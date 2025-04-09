import React, { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Legend);

export default function InvestAI() {
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("1h");
  const [chartData, setChartData] = useState(null);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const backendURL = "http://localhost:8000"; // ajuste se estiver usando outro host

  const handleLogin = async () => {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);

    const res = await fetch(\`\${backendURL}/api/login\`, {
      method: "POST",
      body: form,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    const data = await res.json();
    if (data.access_token) {
      setToken(data.access_token);
    }
  };

  const getRecommendation = async () => {
    if (!token) return alert("Faça login primeiro!");
    setLoading(true);
    const res = await fetch(\`\${backendURL}/api/recommend?symbol=\${symbol}\`, {
      headers: { Authorization: \`Bearer \${token}\` },
    });
    const data = await res.json();
    setRecommendation(data);
    setLoading(false);
  };

  const addFavorite = async () => {
    if (!token) return alert("Faça login primeiro!");
    await fetch(\`\${backendURL}/api/favorite?symbol=\${symbol}\`, {
      method: "POST",
      headers: { Authorization: \`Bearer \${token}\` },
    });
    alert("Favorito salvo!");
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center p-4">
      <h1 className="text-4xl font-bold mb-4">InvestAI</h1>

      {!token && (
        <Card className="max-w-md w-full p-4 mb-6">
          <CardContent>
            <h2 className="text-xl font-semibold mb-2">Login</h2>
            <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Input placeholder="Senha" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <Button onClick={handleLogin} className="mt-2 w-full">Entrar</Button>
          </CardContent>
        </Card>
      )}

      {token && (
        <>
          <Card className="w-full max-w-md p-4 mb-6">
            <CardContent>
              <Input className="mb-2" value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="BTCUSDT" />
              <select className="w-full p-2 border rounded mb-2" onChange={(e) => setInterval(e.target.value)} value={interval}>
                <option value="1m">5 minutos</option>
                <option value="30m">30 minutos</option>
                <option value="1h">1 hora</option>
                <option value="1d">1 dia</option>
              </select>
              <Button onClick={getRecommendation} className="w-full mb-2" disabled={loading}>
                {loading ? "Analisando..." : "Obter Recomendação"}
              </Button>
              <Button onClick={addFavorite} className="w-full" variant="outline">
                Adicionar aos Favoritos
              </Button>
              {recommendation && (
                <div className="mt-4">
                  <p><strong>Recomendação:</strong> {recommendation.signal}</p>
                  <p><strong>Confiança:</strong> {recommendation.confidence}%</p>
                  <p><strong>Horário:</strong> {new Date(recommendation.timestamp).toLocaleString()}</p>
                  <p><strong>Indicadores:</strong></p>
                  <pre className="text-sm bg-gray-200 p-2 rounded">{JSON.stringify(recommendation.indicators, null, 2)}</pre>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
