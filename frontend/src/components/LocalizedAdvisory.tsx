import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Calendar, CircleAlert, CloudRain, CloudSun, Droplets, Sprout, Sun, Thermometer, Wind } from "lucide-react";

interface LocalizedAdvisoryProps {
  location: string;
}

interface WeatherAdvisory {
  type: string;
  message: string;
  impact: string;
  action: string;
  icon: React.ReactNode;
  severity: "info" | "warning" | "alert";
}

interface CropSuggestion {
  name: string;
  suitability: "Excellent" | "Good" | "Average" | "Poor";
  score: number;
  growingSeason: string;
  waterRequirement: "Low" | "Medium" | "High";
  specialNotes: string;
}

interface SeasonalAlert {
  title: string;
  message: string;
  category: "pest" | "disease" | "weather" | "resource";
  timing: string;
  severity: "low" | "medium" | "high";
}

const weatherAdvisories: WeatherAdvisory[] = [
  {
    type: "Rainfall",
    message: "Light to moderate rainfall expected in the next 48 hours",
    impact: "Favorable for early vegetative stage crops, but may affect harvesting activities",
    action: "Consider postponing any planned spraying operations",
    icon: <CloudRain className="h-8 w-8" />,
    severity: "info"
  },
  {
    type: "Temperature",
    message: "Heat wave conditions expected in the coming week",
    impact: "May cause heat stress in sensitive crops and increase water requirements",
    action: "Increase irrigation frequency and consider shade for sensitive crops",
    icon: <Thermometer className="h-8 w-8" />,
    severity: "warning"
  },
  {
    type: "Humidity",
    message: "High humidity levels forecasted",
    impact: "Increases risk of fungal diseases in crops",
    action: "Monitor crops closely and consider preventive fungicide application",
    icon: <Droplets className="h-8 w-8" />,
    severity: "alert"
  }
];

const cropSuggestions: CropSuggestion[] = [
  {
    name: "Rice (IR36)",
    suitability: "Excellent",
    score: 92,
    growingSeason: "June-November",
    waterRequirement: "High",
    specialNotes: "Well-adapted to the local climate and resistant to common pests"
  },
  {
    name: "Tomato (Arka Rakshak)",
    suitability: "Good",
    score: 85,
    growingSeason: "October-March",
    waterRequirement: "Medium",
    specialNotes: "Disease resistant variety suitable for the region"
  },
  {
    name: "Chickpea (JG-14)",
    suitability: "Good",
    score: 80,
    growingSeason: "October-February",
    waterRequirement: "Low",
    specialNotes: "Drought tolerant and good for crop rotation after rice"
  },
  {
    name: "Cotton (Bt hybrid)",
    suitability: "Average",
    score: 65,
    growingSeason: "May-November",
    waterRequirement: "Medium",
    specialNotes: "Consider only with adequate irrigation facilities"
  }
];

const seasonalAlerts: SeasonalAlert[] = [
  {
    title: "Rice Blast Risk",
    message: "Current weather conditions are favorable for rice blast development",
    category: "disease",
    timing: "Next 2 weeks",
    severity: "high"
  },
  {
    title: "Stem Borer Emergence",
    message: "Stem borer populations likely to increase in rice crops",
    category: "pest",
    timing: "Starting next week",
    severity: "medium"
  },
  {
    title: "Water Scarcity Alert",
    message: "Reduced water availability expected for irrigation",
    category: "resource",
    timing: "Coming month",
    severity: "medium"
  },
  {
    title: "Unseasonal Rain Warning",
    message: "Possibility of unseasonal rains which may affect standing crops",
    category: "weather",
    timing: "Next 10 days",
    severity: "low"
  }
];

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case "info":
    case "low":
      return "bg-blue-100 text-blue-800";
    case "warning":
    case "medium":
      return "bg-amber-100 text-amber-800";
    case "alert":
    case "high":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getSuitabilityColor = (suitability: string) => {
  switch (suitability) {
    case "Excellent":
      return "bg-green-100 text-green-800";
    case "Good":
      return "bg-blue-100 text-blue-800";
    case "Average":
      return "bg-amber-100 text-amber-800";
    case "Poor":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
};

const getCategoryIcon = (category: string) => {
  switch (category) {
    case "pest":
      return <CircleAlert className="h-4 w-4 text-amber-500" />;
    case "disease":
      return <CircleAlert className="h-4 w-4 text-red-500" />;
    case "weather":
      return <CloudSun className="h-4 w-4 text-blue-500" />;
    case "resource":
      return <Droplets className="h-4 w-4 text-cyan-500" />;
    default:
      return <CircleAlert className="h-4 w-4" />;
  }
};

const LocalizedAdvisory: React.FC<LocalizedAdvisoryProps> = ({ location }) => {
  const [currentDate] = useState<string>(
    new Date().toLocaleDateString("en-US", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric"
    })
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-start">
            <div>
              <CardTitle>Agricultural Advisory</CardTitle>
              <CardDescription>
                Localized insights for {location}
              </CardDescription>
            </div>
            <div className="flex items-center text-sm text-gray-500">
              <Calendar className="h-4 w-4 mr-1" />
              {currentDate}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="weather">
            <TabsList className="grid grid-cols-3 mb-6">
              <TabsTrigger value="weather">Weather Advisory</TabsTrigger>
              <TabsTrigger value="crops">Crop Suggestions</TabsTrigger>
              <TabsTrigger value="alerts">Seasonal Alerts</TabsTrigger>
            </TabsList>

            <TabsContent value="weather">
              <div className="space-y-6">
                {weatherAdvisories.map((advisory, index) => (
                  <div 
                    key={index} 
                    className={`border rounded-lg overflow-hidden ${
                      advisory.severity === "info" 
                        ? "border-blue-200" 
                        : advisory.severity === "warning" 
                        ? "border-amber-200" 
                        : "border-red-200"
                    }`}
                  >
                    <div className="flex items-start p-4">
                      <div className={`rounded-full p-2 mr-4 ${
                        advisory.severity === "info" 
                          ? "bg-blue-100" 
                          : advisory.severity === "warning" 
                          ? "bg-amber-100" 
                          : "bg-red-100"
                      }`}>
                        {advisory.icon}
                      </div>
                      <div className="flex-1">
                        <div className="flex justify-between items-start mb-2">
                          <h3 className="font-semibold text-lg">
                            {advisory.type} Advisory
                          </h3>
                          <Badge 
                            className={getSeverityColor(advisory.severity)}
                            variant="outline"
                          >
                            {advisory.severity === "info" 
                              ? "Informational" 
                              : advisory.severity === "warning" 
                              ? "Warning" 
                              : "Alert"}
                          </Badge>
                        </div>
                        <p className="mb-2">{advisory.message}</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 text-sm">
                          <div>
                            <p className="font-medium text-gray-700">Potential Impact:</p>
                            <p className="text-gray-600">{advisory.impact}</p>
                          </div>
                          <div>
                            <p className="font-medium text-gray-700">Recommended Action:</p>
                            <p className="text-gray-600">{advisory.action}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="crops">
              <div className="space-y-6">
                <p className="text-sm text-gray-600 mb-4">
                  Based on current climate conditions, soil characteristics, and regional suitability 
                  for {location}, the following crops are recommended:
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {cropSuggestions.map((crop, index) => (
                    <div key={index} className="border rounded-lg overflow-hidden">
                      <div className="bg-gray-50 p-3 flex justify-between items-center border-b">
                        <h3 className="font-medium">{crop.name}</h3>
                        <Badge className={getSuitabilityColor(crop.suitability)}>
                          {crop.suitability} ({crop.score}%)
                        </Badge>
                      </div>
                      <div className="p-4">
                        <div className="grid grid-cols-2 gap-y-2 text-sm mb-3">
                          <div>
                            <p className="text-gray-500">Growing Season</p>
                            <p className="font-medium">{crop.growingSeason}</p>
                          </div>
                          <div>
                            <p className="text-gray-500">Water Need</p>
                            <p className="font-medium">{crop.waterRequirement}</p>
                          </div>
                        </div>
                        <div className="text-sm">
                          <p className="text-gray-500 mb-1">Special Notes</p>
                          <p>{crop.specialNotes}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="alerts">
              <div className="space-y-3">
                {seasonalAlerts.map((alert, index) => (
                  <div key={index} className="flex space-x-4 p-3 border rounded-lg">
                    <div className={`rounded-full h-10 w-10 flex items-center justify-center ${
                      alert.severity === "high" 
                        ? "bg-red-100" 
                        : alert.severity === "medium" 
                        ? "bg-amber-100" 
                        : "bg-blue-100"
                    }`}>
                      {getCategoryIcon(alert.category)}
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between items-start">
                        <h3 className="font-medium">{alert.title}</h3>
                        <Badge className={getSeverityColor(alert.severity)} variant="outline">
                          {alert.severity.charAt(0).toUpperCase() + alert.severity.slice(1)}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{alert.message}</p>
                      <div className="flex justify-between items-center mt-2 text-xs text-gray-500">
                        <span>Category: {alert.category.charAt(0).toUpperCase() + alert.category.slice(1)}</span>
                        <span>Expected: {alert.timing}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Current Agricultural Conditions</CardTitle>
          <CardDescription>
            Environmental factors affecting farming in {location}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-blue-50 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Thermometer className="h-8 w-8 text-red-500 mb-2" />
              <h3 className="text-sm font-medium text-gray-700">Temperature</h3>
              <p className="text-2xl font-bold text-gray-900 my-1">34°C</p>
              <p className="text-xs text-gray-500">Above seasonal average</p>
            </div>
            
            <div className="bg-blue-50 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Droplets className="h-8 w-8 text-blue-500 mb-2" />
              <h3 className="text-sm font-medium text-gray-700">Humidity</h3>
              <p className="text-2xl font-bold text-gray-900 my-1">68%</p>
              <p className="text-xs text-gray-500">Moderate</p>
            </div>
            
            <div className="bg-blue-50 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Wind className="h-8 w-8 text-cyan-500 mb-2" />
              <h3 className="text-sm font-medium text-gray-700">Wind Speed</h3>
              <p className="text-2xl font-bold text-gray-900 my-1">12 km/h</p>
              <p className="text-xs text-gray-500">Light breeze</p>
            </div>
            
            <div className="bg-blue-50 rounded-lg p-4 flex flex-col items-center justify-center text-center">
              <Sun className="h-8 w-8 text-amber-500 mb-2" />
              <h3 className="text-sm font-medium text-gray-700">Solar Radiation</h3>
              <p className="text-2xl font-bold text-gray-900 my-1">High</p>
              <p className="text-xs text-gray-500">Good for photosynthesis</p>
            </div>
          </div>
          
          <div className="mt-6 bg-green-50 rounded-lg p-4">
            <div className="flex items-start">
              <Sprout className="h-6 w-6 text-green-600 mr-3 mt-0.5" />
              <div>
                <h3 className="font-medium text-green-800 mb-1">General Farming Advice</h3>
                <p className="text-sm text-green-700">
                  Current conditions are favorable for most crop growth stages. However, monitor for 
                  increased pest activity due to rising temperatures. Ensure adequate irrigation as 
                  evapotranspiration rates are higher than usual. Consider early morning or evening 
                  for any field operations to avoid peak heat.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default LocalizedAdvisory;
