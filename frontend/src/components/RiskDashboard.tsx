
import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Thermometer, Droplets, Wind, AlertTriangle, CloudRain } from "lucide-react";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import { useTranslation } from "react-i18next";

interface RiskDashboardProps {
  location: string;
}

// Remove hardcoded weather data - we'll use real crop risk data instead

// Default fallback crops if user profile missing
const defaultCrops = ["Rice", "Wheat", "Tomato"];

// Simple alternating pastel colors - green and brown
const getPastelColor = (index: number): string => {
  const pastelColors = [
    "#A8E6A3", // Beautiful pastel green
    "#A8E6A9", // Nice pastel brown/tan
  ];
  
  return pastelColors[index % 2];
};

// Crop-specific risk factors and thresholds
const cropRiskProfiles = {
  "wheat": {
    optimalTemp: { min: 15, max: 25 },
    optimalHumidity: { min: 40, max: 70 },
    pestRiskHumidity: 75,
    frostRisk: 5,
    heatStress: 35,
    droughtTolerance: "medium",
    fungalRisk: { humidity: 80, temp: 20 }
  },
  "maize": {
    optimalTemp: { min: 18, max: 30 },
    optimalHumidity: { min: 50, max: 75 },
    pestRiskHumidity: 70,
    frostRisk: 0,
    heatStress: 35,
    droughtTolerance: "low",
    fungalRisk: { humidity: 75, temp: 25 }
  },
  "rice": {
    optimalTemp: { min: 20, max: 35 },
    optimalHumidity: { min: 70, max: 90 },
    pestRiskHumidity: 85,
    frostRisk: 10,
    heatStress: 40,
    droughtTolerance: "very_low",
    fungalRisk: { humidity: 90, temp: 28 }
  },
  "soybean": {
    optimalTemp: { min: 20, max: 30 },
    optimalHumidity: { min: 60, max: 80 },
    pestRiskHumidity: 75,
    frostRisk: 2,
    heatStress: 32,
    droughtTolerance: "medium",
    fungalRisk: { humidity: 85, temp: 22 }
  },
  "tomato": {
    optimalTemp: { min: 18, max: 28 },
    optimalHumidity: { min: 50, max: 70 },
    pestRiskHumidity: 75,
    frostRisk: 5,
    heatStress: 32,
    droughtTolerance: "low",
    fungalRisk: { humidity: 80, temp: 15 }
  },
  "mustard": {
    optimalTemp: { min: 15, max: 25 },
    optimalHumidity: { min: 40, max: 65 },
    pestRiskHumidity: 70,
    frostRisk: 0,
    heatStress: 30,
    droughtTolerance: "medium",
    fungalRisk: { humidity: 75, temp: 20 }
  },
  "sugarcane": {
    optimalTemp: { min: 25, max: 35 },
    optimalHumidity: { min: 60, max: 85 },
    pestRiskHumidity: 80,
    frostRisk: 8,
    heatStress: 42,
    droughtTolerance: "low",
    fungalRisk: { humidity: 85, temp: 30 }
  }
};

// Function to calculate crop-specific risk
const calculateCropRisk = (cropName: string, weather: any): number => {
  const normalizedName = cropName.toLowerCase().replace(/\s*\([^)]*\)/, '').replace(/\s*\/.*/, '').trim();
  const profile = cropRiskProfiles[normalizedName];
  
  if (!profile) {
    // Fallback to generic calculation for unknown crops
    const temp = weather?.temperature ?? 25;
    const humidity = weather?.humidity ?? 60;
    const rain = weather?.rain_1h ?? 0;
    return Math.min(100, Math.max(0, (humidity - 40) + (temp > 32 ? (temp - 32) * 2 : 0) + (rain > 5 ? 20 : 0)));
  }

  const temp = weather?.temperature ?? 25;
  const humidity = weather?.humidity ?? 60;
  const rain = weather?.rain_1h ?? 0;
  
  let riskScore = 0;
  
  // Temperature stress risk (0-30 points)
  if (temp < profile.optimalTemp.min) {
    const tempDiff = profile.optimalTemp.min - temp;
    riskScore += Math.min(20, tempDiff * 2);
    if (temp < profile.frostRisk) {
      riskScore += 15; // Frost risk bonus
    }
  } else if (temp > profile.optimalTemp.max) {
    const tempDiff = temp - profile.optimalTemp.max;
    riskScore += Math.min(25, tempDiff * 1.5);
    if (temp > profile.heatStress) {
      riskScore += 10; // Heat stress bonus
    }
  }
  
  // Humidity stress risk (0-25 points)
  if (humidity < profile.optimalHumidity.min) {
    const humidityDiff = profile.optimalHumidity.min - humidity;
    riskScore += Math.min(15, humidityDiff * 0.3);
  } else if (humidity > profile.optimalHumidity.max) {
    const humidityDiff = humidity - profile.optimalHumidity.max;
    riskScore += Math.min(20, humidityDiff * 0.4);
  }
  
  // Pest and disease risk (0-25 points)
  if (humidity > profile.pestRiskHumidity) {
    riskScore += Math.min(15, (humidity - profile.pestRiskHumidity) * 0.5);
  }
  
  // Fungal disease risk (0-20 points)
  if (humidity > profile.fungalRisk.humidity && temp > profile.fungalRisk.temp) {
    riskScore += Math.min(20, (humidity - profile.fungalRisk.humidity) * 0.3 + (temp - profile.fungalRisk.temp) * 0.5);
  }
  
  // Drought/water stress (0-15 points)
  if (rain === 0 && humidity < 40) {
    const droughtMultiplier = {
      "very_low": 2.0,
      "low": 1.5,
      "medium": 1.0,
      "high": 0.5
    };
    riskScore += Math.min(15, (40 - humidity) * 0.3 * (droughtMultiplier[profile.droughtTolerance] || 1.0));
  }
  
  // Heavy rain risk (0-10 points)
  if (rain > 10) {
    riskScore += Math.min(10, rain * 0.5);
  }
  
  return Math.min(100, Math.max(0, Math.round(riskScore)));
};

const getRiskColor = (level: number) => {
  if (level < 30) return "bg-green-500";
  if (level < 60) return "bg-yellow-500";
  return "bg-red-500";
};

const WeatherCard: React.FC<{ title: string; value: string; icon: React.ReactNode; className?: string }> = ({ 
  title, value, icon, className 
}) => (
  <Card className={className}>
    <CardContent className="flex items-center p-4">
      <div className="mr-4 text-gray-500">{icon}</div>
      <div>
        <p className="text-sm font-medium text-gray-500">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </CardContent>
  </Card>
);

const RiskDashboard: React.FC<RiskDashboardProps> = ({ location }) => {
  const { t } = useTranslation();
  const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
  const [weather, setWeather] = useState<{
    temperature?: number;
    humidity?: number;
    wind_speed?: number;
    rain_1h?: number;
    description?: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<{
    irrigation?: string;
    pest_alert?: string;
    general_tips?: string;
    harvest_tips?: string;
    fertilizer_tips?: string;
    crop_health?: string;
    crop_specific_alerts?: Record<string, Record<string, string[]>>;
  } | null>(null);
  const [userCrops, setUserCrops] = useState<string[]>([]);

  const { city, state } = useMemo(() => {
    const parts = (location || "").split(",").map((p) => p.trim()).filter(Boolean);
    return { city: parts[0] || "Bengaluru", state: parts[1] };
  }, [location]);

  useEffect(() => {
    const fetchWeather = async () => {
      setLoading(true);
      setError(null);
      try {
        const url = new URL(`${API_BASE}/weather/weather/current`);
        url.searchParams.set("city", city);
        if (state) url.searchParams.set("state", state);
        url.searchParams.set("country", "IN");
        const token = localStorage.getItem("access_token");
        const res = await fetch(url.toString(), {
          headers: {
            Accept: "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || "Failed to fetch weather");
        }
        setWeather(data.weather || null);
        setAlerts(data.farm_alerts || null);
      } catch (e: any) {
        setError(e?.message || "Failed to fetch weather");
      } finally {
        setLoading(false);
      }
    };
    fetchWeather();
  }, [API_BASE, city, state]);

  // Fetch user profile to get primary_crops from backend (MongoDB)
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const token = localStorage.getItem("access_token");
        if (!token) return;
        const res = await fetch(`${API_BASE}/auth/user/me`, {
          headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (res.ok && Array.isArray(data?.primary_crops)) {
          setUserCrops(data.primary_crops);
        }
      } catch (e) {
        // ignore profile errors here; UI will fallback
      }
    };
    fetchProfile();
  }, [API_BASE]);

  // Derive crops to display based on user profile; compute crop-specific risk from weather
  const crops = useMemo(() => {
    const names = (userCrops && userCrops.length > 0) ? userCrops : defaultCrops;
    const temp = weather?.temperature ?? 25;
    const humidity = weather?.humidity ?? 60;
    
    return names.map((name) => {
      const cropRisk = calculateCropRisk(name, weather);
      const normalizedName = name.toLowerCase().replace(/\s*\([^)]*\)/, '').replace(/\s*\/.*/, '').trim();
      const profile = cropRiskProfiles[normalizedName];
      
      // Generate specific threats based on current conditions and crop profile
      const threats = [];
      
      if (profile) {
        // Temperature-based threats
        if (temp < profile.optimalTemp.min) {
          threats.push({
            name: temp < profile.frostRisk ? t('risk_dashboard.threats.frost_damage') : t('risk_dashboard.threats.cold_stress'),
            probability: temp < profile.frostRisk ? t('risk_dashboard.probability.high') : t('risk_dashboard.probability.medium'),
            due: `${Math.round(temp)}°C (${t('risk_dashboard.optimal')} ${profile.optimalTemp.min}-${profile.optimalTemp.max}°C)`
          });
        } else if (temp > profile.optimalTemp.max) {
          threats.push({
            name: temp > profile.heatStress ? t('risk_dashboard.threats.heat_stress') : t('risk_dashboard.threats.temperature_stress'),
            probability: temp > profile.heatStress ? t('risk_dashboard.probability.high') : t('risk_dashboard.probability.medium'), 
            due: `${Math.round(temp)}°C (${t('risk_dashboard.optimal')} ${profile.optimalTemp.min}-${profile.optimalTemp.max}°C)`
          });
        }
        
        // Humidity-based threats
        if (humidity > profile.pestRiskHumidity) {
          threats.push({
            name: t('risk_dashboard.threats.pest_disease'),
            probability: humidity > profile.pestRiskHumidity + 10 ? t('risk_dashboard.probability.high') : t('risk_dashboard.probability.medium'),
            due: `${Math.round(humidity)}% humidity`
          });
        }
        
        if (humidity > profile.fungalRisk.humidity && temp > profile.fungalRisk.temp) {
          threats.push({
            name: t('risk_dashboard.threats.fungal_disease'), 
            probability: t('risk_dashboard.probability.high'),
            due: `${Math.round(humidity)}% humidity + ${Math.round(temp)}°C`
          });
        }
        
        // Drought stress
        if (weather?.rain_1h === 0 && humidity < 40) {
          const severity = profile.droughtTolerance === "very_low" ? t('risk_dashboard.probability.high') : 
                         profile.droughtTolerance === "low" ? t('risk_dashboard.probability.medium') : t('risk_dashboard.probability.low');
          threats.push({
            name: t('risk_dashboard.threats.drought_stress'),
            probability: severity,
            due: `No rain + ${Math.round(humidity)}% humidity`
          });
        }
      }
      
      // Fallback threat if no specific threats identified
      if (threats.length === 0) {
        threats.push({
          name: t('risk_dashboard.threats.weather_stress'),
          probability: cropRisk > 60 ? t('risk_dashboard.probability.high') : cropRisk > 30 ? t('risk_dashboard.probability.medium') : t('risk_dashboard.probability.low'),
          due: `${Math.round(temp)}°C / ${Math.round(humidity)}%`
        });
      }
      
      return {
        name,
        riskLevel: cropRisk,
        threats: threats.slice(0, 3) // Limit to top 3 threats
      };
    });
  }, [userCrops, weather]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>{t('risk_dashboard.current_weather')}</CardTitle>
            <CardDescription>
              {t('risk_dashboard.weather_description', { location })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-gray-500">{t('risk_dashboard.loading')}</div>
            ) : error ? (
              <div className="text-sm text-red-600">{t('risk_dashboard.error')}</div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                <WeatherCard 
                  title={t('risk_dashboard.temperature')} 
                  value={weather?.temperature !== undefined ? `${Math.round(weather.temperature)}°C` : "-"} 
                  icon={<Thermometer className="w-6 h-6" />} 
                  className="bg-orange-50"
                />
                <WeatherCard 
                  title={t('risk_dashboard.humidity')} 
                  value={weather?.humidity !== undefined ? `${weather.humidity}%` : "-"} 
                  icon={<Droplets className="w-6 h-6" />} 
                  className="bg-blue-50"
                />
                <WeatherCard 
                  title={t('risk_dashboard.wind_speed')} 
                  value={weather?.wind_speed !== undefined ? `${weather.wind_speed} m/s` : "-"} 
                  icon={<Wind className="w-6 h-6" />} 
                  className="bg-green-50"
                />
                <WeatherCard 
                  title={t('risk_dashboard.rainfall')} 
                  value={weather?.rain_1h !== undefined ? `${weather.rain_1h} mm` : "0 mm"} 
                  icon={<CloudRain className="w-6 h-6" />} 
                  className="bg-teal-50"
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('risk_dashboard.risk_distribution')}</CardTitle>
            <CardDescription>{t('risk_dashboard.risk_distribution_description')}</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={crops} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="name" 
                  angle={-45}
                  textAnchor="end"
                  height={80}
                  interval={0}
                />
                <YAxis 
                  label={{ value: t('risk_dashboard.chart_risk_level'), angle: -90, position: 'insideLeft' }}
                  domain={[0, 25]}
                  ticks={[0, 5, 10, 15, 20, 25]}
                />
                <Tooltip 
                  formatter={(value) => [`${value}%`, t('risk_dashboard.chart_risk_level_short')]}
                  labelFormatter={(label) => `${t('risk_dashboard.chart_crop')} ${label}`}
                />
                <Bar 
                  dataKey="riskLevel" 
                  radius={[4, 4, 0, 0]}
                >
                  {crops.map((crop, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={getPastelColor(index)} 
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('risk_dashboard.crop_risk_assessment')}</CardTitle>
          <CardDescription>
            {t('risk_dashboard.crop_risk_description')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {crops.map((crop) => (
              <div key={crop.name}>
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">{crop.name}</h3>
                  <span className="text-sm font-medium">
                    {t('risk_dashboard.risk_level')}: {crop.riskLevel}%
                  </span>
                </div>
                <Progress 
                  value={crop.riskLevel} 
                  className={`h-2 ${getRiskColor(crop.riskLevel)}`} 
                />
                
                <div className="mt-4 bg-gray-50 p-3 rounded-md">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-sm">{t('risk_dashboard.potential_threats')}</h4>
                      <ul className="mt-1 space-y-1">
                        {crop.threats.map((threat, idx) => (
                          <li key={idx} className="text-sm flex justify-between">
                            <span>{threat.name}</span>
                            <span className="text-gray-500 text-xs">
                              {threat.probability} ({threat.due})
                            </span>
                          </li>
                        ))}
                      </ul>
                      
                      {/* Crop-specific recommendations */}
                      {(() => {
                        if (!alerts?.crop_specific_alerts) return null;
                        const direct = alerts.crop_specific_alerts[crop.name];
                        const matchKey = direct
                          ? crop.name
                          : Object.keys(alerts.crop_specific_alerts).find(
                              (key) => key.toLowerCase() === crop.name.toLowerCase()
                            );
                        const cropAlerts = matchKey
                          ? alerts.crop_specific_alerts[matchKey]
                          : null;
                        if (!cropAlerts) return null;
                        const entries = Object.entries(cropAlerts).filter(([, messages]) => messages?.length);
                        if (entries.length === 0) return null;

                        const categoryIcons = {
                          irrigation: "💧",
                          pest_alert: "🐛",
                          harvest_tips: "🌾",
                          fertilizer_tips: "🧪",
                          crop_health: "🌱"
                        };

                        const categoryColors = {
                          irrigation: "bg-blue-50 border-blue-200",
                          pest_alert: "bg-red-50 border-red-200", 
                          harvest_tips: "bg-green-50 border-green-200",
                          fertilizer_tips: "bg-purple-50 border-purple-200",
                          crop_health: "bg-yellow-50 border-yellow-200"
                        };

                        return (
                          <div className="mt-4">
                            <h4 className="font-semibold text-sm text-gray-800 mb-3 flex items-center">
                              <span className="mr-2">🎯</span>
                              {crop.name} {t('risk_dashboard.specific_recommendations')}
                            </h4>
                            <div className="space-y-3">
                              {entries.map(([category, messages]) => (
                                <div 
                                  key={category} 
                                  className={`p-3 rounded-lg border ${categoryColors[category] || "bg-gray-50 border-gray-200"}`}
                                >
                                  <div className="flex items-center mb-2">
                                    <span className="text-lg mr-2">
                                      {categoryIcons[category] || "📋"}
                                    </span>
                                    <h5 className="font-medium text-sm text-gray-800 capitalize">
                                      {t(`risk_dashboard.categories.${category}`)}
                                    </h5>
                                  </div>
                                  <div className="space-y-1">
                                    {messages.map((message, idx) => (
                                      <p key={idx} className="text-sm text-gray-700 leading-relaxed">
                                        {message}
                                      </p>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default RiskDashboard;
