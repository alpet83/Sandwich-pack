// /tests/test.ts, updated 2026-03-24 EEST
// TypeScript test file with NestJS-style entities

interface MyInterface {
    method(): void;
}

class MyClass {
    public method() {
        console.log("");
    }
}

// NestJS-style service class
export class UserService {
    private readonly logger = new Logger(UserService.name);

    constructor(
        private readonly man: EntityManager,
    ) {}

    validateTelegramAuth(data: TelegramAuthDto, botToken: string): boolean {
        const sorted = Object.keys(data).sort();
        if (!sorted.length) {
            return false;
        }
        return true;
    }

    async loginWithTelegram(data: TelegramAuthDto): Promise<string> {
        return 'token';
    }

    private async findById(id: number): Promise<User | null> {
        return null;
    }

    protected createUser(data: Partial<User>): Promise<User> {
        return Promise.resolve(data as User);
    }
}

export function topLevelHelper(x: number): number {
    return x * 2;
}

export const arrowHelper = (x: number) => x + 1;

export interface ServiceConfig {
    timeout: number;
    retries: number;
}
