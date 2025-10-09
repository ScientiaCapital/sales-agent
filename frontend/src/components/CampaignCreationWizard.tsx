/**
 * Campaign Creation Wizard Component
 *
 * Multi-step form for creating outreach campaigns with targeting and message templates
 */

import { useState } from 'react';
import type { CampaignCreateRequest } from '../types';

interface CampaignCreationWizardProps {
  onComplete: (campaign: CampaignCreateRequest) => Promise<void>;
  onCancel: () => void;
}

type WizardStep = 1 | 2 | 3 | 4;

const INDUSTRIES = [
  'Technology',
  'SaaS',
  'Enterprise Software',
  'Healthcare',
  'Finance',
  'E-commerce',
  'Manufacturing',
  'Education',
  'Real Estate',
  'Retail',
];

const COMPANY_SIZES = [
  '1-10',
  '11-50',
  '51-200',
  '201-500',
  '501-1000',
  '1000+',
];

export function CampaignCreationWizard({
  onComplete,
  onCancel,
}: CampaignCreationWizardProps) {
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<CampaignCreateRequest>({
    name: '',
    channel: 'email',
    min_qualification_score: 70,
    target_industries: [],
    target_company_sizes: [],
    message_template: '',
    custom_context: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const updateFormData = (updates: Partial<CampaignCreateRequest>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
    // Clear errors for updated fields
    setErrors((prev) => {
      const newErrors = { ...prev };
      Object.keys(updates).forEach((key) => delete newErrors[key]);
      return newErrors;
    });
  };

  const validateStep = (step: WizardStep): boolean => {
    const newErrors: Record<string, string> = {};

    if (step === 1) {
      if (!formData.name.trim()) {
        newErrors.name = 'Campaign name is required';
      }
      if (!formData.channel) {
        newErrors.channel = 'Please select a channel';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 4) as WizardStep);
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1) as WizardStep);
  };

  const handleSubmit = async () => {
    if (!validateStep(currentStep)) return;

    setIsSubmitting(true);
    try {
      await onComplete(formData);
    } catch (error) {
      setErrors({
        submit: error instanceof Error ? error.message : 'Failed to create campaign',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleIndustry = (industry: string) => {
    const current = formData.target_industries || [];
    updateFormData({
      target_industries: current.includes(industry)
        ? current.filter((i) => i !== industry)
        : [...current, industry],
    });
  };

  const toggleCompanySize = (size: string) => {
    const current = formData.target_company_sizes || [];
    updateFormData({
      target_company_sizes: current.includes(size)
        ? current.filter((s) => s !== size)
        : [...current, size],
    });
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-20 mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-2xl font-bold text-gray-900">Create Campaign</h3>
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600"
            disabled={isSubmitting}
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {[1, 2, 3, 4].map((step) => (
              <div key={step} className="flex items-center flex-1">
                <div
                  className={`flex items-center justify-center w-10 h-10 rounded-full border-2 ${
                    step <= currentStep
                      ? 'border-indigo-600 bg-indigo-600 text-white'
                      : 'border-gray-300 bg-white text-gray-500'
                  }`}
                >
                  {step}
                </div>
                {step < 4 && (
                  <div
                    className={`flex-1 h-1 mx-2 ${
                      step < currentStep ? 'bg-indigo-600' : 'bg-gray-300'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-2 text-sm text-gray-600">
            <span>Basic Info</span>
            <span>Targeting</span>
            <span>Template</span>
            <span>Review</span>
          </div>
        </div>

        {/* Step Content */}
        <div className="mb-8 min-h-[400px]">
          {/* Step 1: Basic Info */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                  Campaign Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => updateFormData({ name: e.target.value })}
                  className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    errors.name ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="e.g., Enterprise SaaS Q1 Outreach"
                />
                {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
              </div>

              <div>
                <label htmlFor="channel" className="block text-sm font-medium text-gray-700 mb-2">
                  Channel <span className="text-red-500">*</span>
                </label>
                <select
                  id="channel"
                  value={formData.channel}
                  onChange={(e) =>
                    updateFormData({ channel: e.target.value as 'email' | 'linkedin' | 'sms' })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="email">Email</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="sms">SMS</option>
                </select>
              </div>

              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description (Optional)
                </label>
                <textarea
                  id="description"
                  value={formData.custom_context || ''}
                  onChange={(e) => updateFormData({ custom_context: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Brief description of campaign goals..."
                />
              </div>
            </div>
          )}

          {/* Step 2: Targeting */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <label htmlFor="score" className="block text-sm font-medium text-gray-700 mb-2">
                  Minimum Qualification Score: {formData.min_qualification_score}
                </label>
                <input
                  type="range"
                  id="score"
                  min="0"
                  max="100"
                  step="5"
                  value={formData.min_qualification_score}
                  onChange={(e) =>
                    updateFormData({ min_qualification_score: parseInt(e.target.value) })
                  }
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0</span>
                  <span>50</span>
                  <span>100</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Industries
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {INDUSTRIES.map((industry) => (
                    <label key={industry} className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.target_industries?.includes(industry) || false}
                        onChange={() => toggleIndustry(industry)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-gray-700">{industry}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Target Company Sizes
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {COMPANY_SIZES.map((size) => (
                    <label key={size} className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.target_company_sizes?.includes(size) || false}
                        onChange={() => toggleCompanySize(size)}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-gray-700">{size}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Message Template */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div>
                <label htmlFor="template" className="block text-sm font-medium text-gray-700 mb-2">
                  Message Template
                </label>
                <p className="text-sm text-gray-500 mb-2">
                  Use {'{{company_name}}'}, {'{{contact_name}}'}, {'{{industry}}'} as placeholders
                </p>
                <textarea
                  id="template"
                  value={formData.message_template || ''}
                  onChange={(e) => updateFormData({ message_template: e.target.value })}
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                  placeholder="Hi {{contact_name}},&#10;&#10;I noticed {{company_name}} is in the {{industry}} space..."
                />
              </div>

              <div>
                <label htmlFor="context" className="block text-sm font-medium text-gray-700 mb-2">
                  Additional Context for AI Generation
                </label>
                <textarea
                  id="context"
                  value={formData.custom_context || ''}
                  onChange={(e) => updateFormData({ custom_context: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Focus on ROI, enterprise security features, etc."
                />
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                <p className="text-sm text-blue-800">
                  <strong>Preview:</strong> AI will generate 3 variants (Professional, Friendly, Direct) based on this template
                </p>
              </div>
            </div>
          )}

          {/* Step 4: Review */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div className="bg-gray-50 rounded-lg p-6 space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-gray-500">Campaign Name</h4>
                  <p className="text-lg font-semibold text-gray-900">{formData.name}</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Channel</h4>
                    <p className="text-base text-gray-900 capitalize">{formData.channel}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Min Score</h4>
                    <p className="text-base text-gray-900">{formData.min_qualification_score}</p>
                  </div>
                </div>

                {formData.target_industries && formData.target_industries.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Target Industries</h4>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {formData.target_industries.map((industry) => (
                        <span
                          key={industry}
                          className="px-3 py-1 bg-indigo-100 text-indigo-800 text-sm rounded-full"
                        >
                          {industry}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {formData.target_company_sizes && formData.target_company_sizes.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Company Sizes</h4>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {formData.target_company_sizes.map((size) => (
                        <span
                          key={size}
                          className="px-3 py-1 bg-green-100 text-green-800 text-sm rounded-full"
                        >
                          {size}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {formData.message_template && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-500">Message Template</h4>
                    <pre className="mt-2 p-3 bg-white border border-gray-200 rounded text-sm whitespace-pre-wrap">
                      {formData.message_template}
                    </pre>
                  </div>
                )}
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                <p className="text-sm text-yellow-800">
                  <strong>Next Steps:</strong> After creation, use "Generate Messages" to create AI-powered variants
                </p>
              </div>

              {errors.submit && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <p className="text-sm text-red-800">{errors.submit}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between">
          <button
            onClick={currentStep === 1 ? onCancel : handleBack}
            disabled={isSubmitting}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {currentStep === 1 ? 'Cancel' : 'Back'}
          </button>

          {currentStep < 4 ? (
            <button
              onClick={handleNext}
              className="px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center space-x-2"
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Creating...</span>
                </>
              ) : (
                <span>Create Campaign</span>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
