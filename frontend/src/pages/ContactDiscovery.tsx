/**
 * Contact Discovery Page
 * 
 * ATL contact search, social media activity, and relationship graphs
 */

import { useState, memo } from 'react';
import type { Contact, SocialActivity, RelationshipNode } from '../types';

export const ContactDiscovery = memo(() => {
  const [searchQuery, setSearchQuery] = useState('');
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [activities, setActivities] = useState<SocialActivity[]>([]);

  // Mock data for demonstration
  const mockContacts: Contact[] = [
    {
      id: '1',
      name: 'John Smith',
      title: 'CTO',
      company: 'TechCorp',
      email: 'john@techcorp.com',
      linkedin_url: 'https://linkedin.com/in/johnsmith',
      twitter_handle: '@johnsmith',
      social_activity_score: 85,
    },
    {
      id: '2',
      name: 'Jane Doe',
      title: 'VP Engineering',
      company: 'DataInc',
      linkedin_url: 'https://linkedin.com/in/janedoe',
      social_activity_score: 92,
    },
  ];

  const mockActivities: SocialActivity[] = [
    {
      id: '1',
      contact_id: '1',
      platform: 'linkedin',
      activity_type: 'post',
      content: 'Excited to announce our new AI infrastructure platform...',
      timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      engagement_score: 250,
    },
    {
      id: '2',
      contact_id: '1',
      platform: 'twitter',
      activity_type: 'comment',
      content: 'Great insights on scaling ML systems @aiconf',
      timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
      engagement_score: 85,
    },
  ];

  const handleSearch = () => {
    if (searchQuery) {
      setContacts(mockContacts);
    }
  };

  const handleSelectContact = (contact: Contact) => {
    setSelectedContact(contact);
    setActivities(mockActivities);
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Contact Discovery</h1>
        <p className="text-gray-600 mt-2">
          Find and track decision makers with social intelligence
        </p>
      </div>

      {/* Search */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex gap-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search by name, title, or company..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Search Contacts
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact List */}
        <div className="lg:col-span-1 bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">
            Contacts ({contacts.length})
          </h2>

          <div className="space-y-3">
            {contacts.map((contact) => (
              <div
                key={contact.id}
                onClick={() => handleSelectContact(contact)}
                className={`
                  p-4 border rounded-lg cursor-pointer transition-colors
                  ${selectedContact?.id === contact.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300'
                  }
                `}
              >
                <div className="font-medium text-gray-900">{contact.name}</div>
                <div className="text-sm text-gray-600">
                  {contact.title} at {contact.company}
                </div>
                <div className="mt-2 flex items-center space-x-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-green-600 h-2 rounded-full"
                      style={{
                        width: `${contact.social_activity_score}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">
                    {contact.social_activity_score}
                  </span>
                </div>
              </div>
            ))}

            {contacts.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                Search for contacts to get started
              </div>
            )}
          </div>
        </div>

        {/* Contact Details & Activity */}
        <div className="lg:col-span-2 space-y-6">
          {selectedContact ? (
            <>
              {/* Contact Info */}
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">
                      {selectedContact.name}
                    </h2>
                    <p className="text-gray-600 mt-1">
                      {selectedContact.title} at {selectedContact.company}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-bold text-green-600">
                      {selectedContact.social_activity_score}
                    </div>
                    <div className="text-xs text-gray-500">Activity Score</div>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-4">
                  {selectedContact.email && (
                    <div>
                      <div className="text-sm text-gray-600">Email</div>
                      <div className="font-medium">{selectedContact.email}</div>
                    </div>
                  )}
                  {selectedContact.phone && (
                    <div>
                      <div className="text-sm text-gray-600">Phone</div>
                      <div className="font-medium">{selectedContact.phone}</div>
                    </div>
                  )}
                  {selectedContact.linkedin_url && (
                    <div>
                      <div className="text-sm text-gray-600">LinkedIn</div>
                      <a
                        href={selectedContact.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        View Profile
                      </a>
                    </div>
                  )}
                  {selectedContact.twitter_handle && (
                    <div>
                      <div className="text-sm text-gray-600">Twitter</div>
                      <div className="font-medium">
                        {selectedContact.twitter_handle}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Social Activity Timeline */}
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">
                  Recent Activity
                </h3>

                <div className="space-y-4">
                  {activities.map((activity) => (
                    <div
                      key={activity.id}
                      className="flex items-start space-x-3 p-4 bg-gray-50 rounded-lg"
                    >
                      <div className="flex-shrink-0">
                        {activity.platform === 'linkedin' && (
                          <span className="text-2xl">💼</span>
                        )}
                        {activity.platform === 'twitter' && (
                          <span className="text-2xl">🐦</span>
                        )}
                        {activity.platform === 'github' && (
                          <span className="text-2xl">💻</span>
                        )}
                      </div>

                      <div className="flex-1">
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-sm font-medium text-gray-900 capitalize">
                            {activity.activity_type}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(activity.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">
                          {activity.content}
                        </p>
                        <div className="mt-2 text-xs text-gray-500">
                          Engagement: {activity.engagement_score}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Relationship Graph Placeholder */}
              <div className="bg-white shadow rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">
                  Relationship Network
                </h3>
                <div className="h-64 bg-gray-100 rounded-lg flex items-center justify-center">
                  <p className="text-gray-500">
                    Relationship graph visualization coming soon
                  </p>
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white shadow rounded-lg p-12 text-center">
              <div className="text-6xl mb-4">👤</div>
              <p className="text-gray-500">
                Select a contact to view details and activity
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

ContactDiscovery.displayName = 'ContactDiscovery';

export default ContactDiscovery;
