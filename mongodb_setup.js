/**
 * MongoDB Collection Definitions
 * Academy Program - Phase 1
 * 
 * Run this in MongoDB shell or use mongosh to create
 * the collections and indexes.
 */

// Switch to the academy database
use academy_identity;

// ============================================================
// Users Collection
// Stores identity, authentication, and role information
// ============================================================

// Create users collection with validation
db.createCollection("users", {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["user_id", "email", "name", "role", "status", "auth", "metadata"],
            properties: {
                user_id: {
                    bsonType: "string",
                    description: "UUID - stable user identifier"
                },
                email: {
                    bsonType: "string",
                    pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                    description: "User email address - must be unique"
                },
                name: {
                    bsonType: "string",
                    description: "User's full name"
                },
                role: {
                    enum: ["student", "teacher", "store", "admin"],
                    description: "User role in the system"
                },
                status: {
                    enum: ["uninitialised", "active", "inactive", "deleted"],
                    description: "Account status"
                },
                auth: {
                    bsonType: "object",
                    required: ["password_hash", "password_last_changed"],
                    properties: {
                        password_hash: {
                            bsonType: "string",
                            description: "Bcrypt hashed password"
                        },
                        password_last_changed: {
                            bsonType: "date",
                            description: "Timestamp of last password change"
                        }
                    }
                },
                associations: {
                    bsonType: "object",
                    properties: {
                        classes: {
                            bsonType: "array",
                            items: {
                                bsonType: "string"
                            },
                            description: "List of class UUIDs the user is associated with"
                        },
                        programs: {
                            bsonType: "array",
                            items: {
                                bsonType: "string"
                            },
                            description: "List of program UUIDs the user is associated with"
                        }
                    }
                },
                metadata: {
                    bsonType: "object",
                    required: ["created_at"],
                    properties: {
                        created_at: {
                            bsonType: "date",
                            description: "Account creation timestamp"
                        },
                        last_login: {
                            bsonType: ["date", "null"],
                            description: "Last successful login timestamp"
                        }
                    }
                }
            }
        }
    },
    validationLevel: "moderate",
    validationAction: "error"
});

// Create indexes
db.users.createIndex({ "user_id": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "role": 1 });
db.users.createIndex({ "status": 1 });
db.users.createIndex({ "email": 1, "status": 1 });

print("Users collection created with indexes");

// ============================================================
// Sample Admin User for Initial Setup
// Password: "admin123" (change immediately in production!)
// ============================================================

// Note: This creates an initial admin user for bootstrapping.
// The password hash is for "admin123" using bcrypt.
// In production, create this user through a secure setup script.

db.users.insertOne({
    user_id: "00000000-0000-0000-0000-000000000001",
    email: "admin@academy.local",
    name: "System Administrator",
    role: "admin",
    status: "active",
    auth: {
        // Hash for "admin123" - CHANGE IN PRODUCTION
        password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4qSQlH1NXcqJkHdm",
        password_last_changed: new Date()
    },
    associations: {
        classes: [],
        programs: []
    },
    metadata: {
        created_at: new Date(),
        last_login: null
    }
});

print("Admin user created - email: admin@academy.local, password: admin123");
print("WARNING: Change the admin password immediately in production!");
