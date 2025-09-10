import React from 'react';
import Icon from '../../../components/AppIcon';

const AIAnalysis = ({ event, analysis }) => {
  const getSeverityColor = (severity) => {
    if (severity >= 9) return 'text-red-600 bg-red-50 border-red-200';
    if (severity >= 7) return 'text-orange-600 bg-orange-50 border-orange-200';
    if (severity >= 4) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-green-600 bg-green-50 border-green-200';
  };

  const getSeverityIcon = (severity) => {
    if (severity >= 9) return 'AlertTriangle';
    if (severity >= 7) return 'AlertCircle';
    if (severity >= 4) return 'Info';
    return 'CheckCircle';
  };

  const getThreatLevel = (severity) => {
    if (severity >= 9) return 'Critical';
    if (severity >= 7) return 'High';
    if (severity >= 4) return 'Medium';
    return 'Low';
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 90) return 'text-green-600';
    if (confidence >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* AI Severity Assessment */}
      <div className={`p-6 rounded-lg border-2 ${getSeverityColor(analysis?.aiSeverity)}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <Icon name={getSeverityIcon(analysis?.aiSeverity)} size={24} />
            <div>
              <h3 className="text-lg font-semibold">AI Threat Assessment</h3>
              <p className="text-sm opacity-80">Automated analysis powered by machine learning</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold">{analysis?.aiSeverity}/10</div>
            <div className="text-sm font-medium">{getThreatLevel(analysis?.aiSeverity)} Risk</div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="text-center p-3 bg-white/50 rounded-md">
            <div className="text-lg font-semibold">{analysis?.confidence}%</div>
            <div className={`text-sm font-medium ${getConfidenceColor(analysis?.confidence)}`}>
              Confidence Level
            </div>
          </div>
          <div className="text-center p-3 bg-white/50 rounded-md">
            <div className="text-lg font-semibold">{analysis?.riskScore}</div>
            <div className="text-sm font-medium">Risk Score</div>
          </div>
          <div className="text-center p-3 bg-white/50 rounded-md">
            <div className="text-lg font-semibold">{analysis?.threatCategory}</div>
            <div className="text-sm font-medium">Threat Type</div>
          </div>
        </div>
      </div>
      {/* AI Explanation */}
      <div className="space-y-4">
        <h4 className="text-md font-semibold text-foreground flex items-center space-x-2">
          <Icon name="Brain" size={20} />
          <span>AI Analysis Explanation</span>
        </h4>
        <div className="p-4 bg-muted rounded-md">
          <p className="text-sm text-foreground leading-relaxed">{analysis?.explanation}</p>
        </div>
      </div>
      {/* Threat Indicators */}
      <div className="space-y-4">
        <h4 className="text-md font-semibold text-foreground flex items-center space-x-2">
          <Icon name="Target" size={20} />
          <span>Threat Indicators</span>
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {analysis?.indicators?.map((indicator, index) => (
            <div key={index} className="flex items-center space-x-3 p-3 bg-muted rounded-md">
              <Icon 
                name={indicator?.severity >= 7 ? 'AlertTriangle' : 'Info'} 
                size={16} 
                className={indicator?.severity >= 7 ? 'text-red-500' : 'text-yellow-500'} 
              />
              <div className="flex-1">
                <div className="text-sm font-medium text-foreground">{indicator?.type}</div>
                <div className="text-xs text-muted-foreground">{indicator?.description}</div>
              </div>
              <div className={`text-xs font-medium px-2 py-1 rounded ${
                indicator?.severity >= 7 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
              }`}>
                {indicator?.severity}/10
              </div>
            </div>
          ))}
        </div>
      </div>
      {/* Recommendations */}
      <div className="space-y-4">
        <h4 className="text-md font-semibold text-foreground flex items-center space-x-2">
          <Icon name="Lightbulb" size={20} />
          <span>Recommended Actions</span>
        </h4>
        <div className="space-y-3">
          {analysis?.recommendations?.map((recommendation, index) => (
            <div key={index} className="flex items-start space-x-3 p-4 bg-blue-50 border border-blue-200 rounded-md">
              <Icon name="ArrowRight" size={16} className="text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <div className="text-sm font-medium text-blue-900 mb-1">{recommendation?.action}</div>
                <div className="text-xs text-blue-700">{recommendation?.description}</div>
                <div className="flex items-center space-x-4 mt-2">
                  <span className={`text-xs px-2 py-1 rounded ${
                    recommendation?.priority === 'High' ? 'bg-red-100 text-red-700' :
                    recommendation?.priority === 'Medium'? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {recommendation?.priority} Priority
                  </span>
                  <span className="text-xs text-blue-600">
                    ETA: {recommendation?.estimatedTime}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      {/* MITRE ATT&CK Mapping */}
      {analysis?.mitreMapping && (
        <div className="space-y-4">
          <h4 className="text-md font-semibold text-foreground flex items-center space-x-2">
            <Icon name="Shield" size={20} />
            <span>MITRE ATT&CK Framework</span>
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {analysis?.mitreMapping?.map((mapping, index) => (
              <div key={index} className="p-4 border border-border rounded-md">
                <div className="flex items-center space-x-2 mb-2">
                  <Icon name="Target" size={16} className="text-red-500" />
                  <span className="text-sm font-medium text-foreground">{mapping?.technique}</span>
                </div>
                <div className="text-xs text-muted-foreground mb-2">{mapping?.description}</div>
                <div className="text-xs font-mono text-blue-600">{mapping?.id}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AIAnalysis;