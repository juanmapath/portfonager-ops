# Documentación de la API - proftview

Esta API proporciona acceso a la configuración y datos de los bots de trading en el sistema.

**URL Base:** `/api/proftview/`

---

## 0. Autenticación (Authentication)

Todos los endpoints que implican **modificación de datos** (POST, PUT, DELETE, etc.) requieren que el usuario esté autenticado y sea un **Superusuario** de Django. Sin embargo, las vistas de **solo lectura** (GET) son públicas y no requieren token.

Se utiliza **Token Authentication** de Django Rest Framework para las operaciones protegidas.

### Cabecera de Autorización
Las peticiones protegidas deben incluir la siguiente cabecera HTTP:
`Authorization: Token <tu_token_aqui>`

### 0.1 Login (Obtener Token)
**Endpoint:** `POST /auth/login/`

Permite obtener un token de acceso proporcionando credenciales de superusuario.

**Cuerpo (JSON):**
- `username`: Nombre de usuario.
- `password`: Contraseña.

**Respuesta Exitosa (200 OK):**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

### 0.2 Verificar Token
**Endpoint:** `GET /auth/verify/` [PROTEGIDO]

Permite verificar si un token sigue siendo válido y si el usuario asociado tiene permisos de superusuario.

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/auth/verify/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "message": "Token is valid",
  "user": "admin"
}
```

---

## 1. Familias (Families) [PÚBLICO - GET]

Las familias agrupan diferentes bots bajo una misma categoría o estrategia general.

Las familias agrupan diferentes bots bajo una misma categoría o estrategia general.

### Listar Familias
**Endpoint:** `GET /families/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/families/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "name": "Speculator Family",
    "active": true,
    "folder": "speculator_bots"
  },
  {
    "id": 2,
    "name": "Market Maker Family",
    "active": true,
    "folder": "mm_bots"
  }
]
```

### Detalle de Familia
**Endpoint:** `GET /families/{id}/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/families/1/
```

**Ejemplo de Respuesta:**
```json
{
  "id": 1,
  "name": "Speculator Family",
  "active": true,
  "folder": "speculator_bots"
}
```

---

## 2. Bots

Representa la configuración individual de cada bot.

### Listar Bots
**Endpoint:** `GET /bots/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/bots/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "family": 1,
    "name": "BitTrader Bot",
    "strategy_type": "OneStrategy",
    "folder": "bit_trader",
    "execute_minute": 55,
    "summer_operate_hour": 14,
    "winter_operate_hour": 13,
    "active": true,
    "capital_active": 5000.0,
    "cap_value": 5200.0,
    "cap_ingresado": 5000.0,
    "cap_no_asignado": 0.0,
    "cap_to_add": 0.0,
    "cap_retirado": 0.0,
    "pnl_real": 200.0,
    "pnl_unreal": 50.0,
    "rets": 0.04,
    "tg_key1": "XXXX",
    "tg_key2": "YYYY",
    "tp": 0.05,
    "sl": 0.02
  }
]
```

---

## 3. Brokers

Configuración de los intermediarios financieros (brokers) utilizados.

### Listar Brokers
**Endpoint:** `GET /brokers/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/brokers/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "name": "Interactive Brokers",
    "coms": 1.0
  },
  {
    "id": 2,
    "name": "Binance",
    "coms": 0.1
  }
]
```

---

## 4. Activos del Bot (Bot Assets)

Información detallada sobre los activos en los que opera cada bot. Permite filtrado avanzado.

### Listar Activos
**Endpoint:** `GET /assets/`

**Parámetros de Consulta (Query Params):**
- `family`: (Opcional) ID de la familia.
- `bot`: (Opcional) ID del bot.
- `broker`: (Opcional) ID del broker.

**Ejemplo de Llamado (con filtros):**
```bash
curl -X GET "http://localhost:8000/api/proftview/assets/?family=1&bot=1"
```

**Ejemplo de Respuesta:**
```json
{
  "id": 1,
  "bot": 1,
  "bot_name": "BitTrader Bot",
  "family_name": "Speculator Family",
  "broker_name": "Binance",
  "operate": true,
  "asset": "BTC/USDT",
  "params1": "volatilidad_alta",
  "params2": null,
  "params3": null,
  "alloc": 0.5,
  "broker": 2,
  "position": 1,
  "qty_open": 0.05,
  "cap_to_trade": 2500.0,
  "cap_to_add": 0.0,
  "cap_value_in_trade": 2550.0,
  "op_price": 45000.0,
  "last_price": 51000.0,
  "pnl_un": 50.0,
  "capAdded": 0.0,
  "PNL": 200.0,
  "trades": 15.0,
  "coms": 5.0,
  "created_date": "2024-03-19",
  "updated_date": "2024-03-19",
  "stats1": { "win_rate": 0.65 },
  "stats2": null
}
```

### Agregación de Activos (Totales)
**Endpoint:** `GET /assets/aggregated/`

Devuelve una sumatoria (agregación) de los campos más importantes de los `BotAsset` filtrados, así como el capital no asignado (`cap_no_asignado`) del `Bot` o `Bots` involucrados, y el total del capital añadido (`capAdded` de `BotAsset` + `cap_no_asignado` de `Bot`).

**Parámetros de Consulta (Query Params):**
- `bot`: (Opcional) ID del bot.
- `broker`: (Opcional) ID del broker.
- `family`: (Opcional) ID de la familia.

**Ejemplo de Llamado:**
```bash
curl -X GET "http://localhost:8000/api/proftview/assets/aggregated/?family=1&bot=1"
```

**Ejemplo de Respuesta:**
```json
{
  "cap_to_add_sum": 0.0,
  "cap_value_in_trade_sum": 2550.0,
  "pnl_un_sum": 50.0,
  "PNL_sum": 200.0,
  "coms_sum": 5.0,
  "trades_sum": 15.0,
  "cap_to_trade_sum": 2500.0,
  "capAdded_sum": 1000.0,
  "cap_no_asignado": 0.0,
  "total_capital_added": 1000.0
}
```

### Adición de Capital a Activo (BotAsset)
**Endpoint:** `POST /assets/add-capital/`

Permite añadir capital al campo `cap_to_add` de un `BotAsset` específico y registrar una transacción.

**Cuerpo de la Petición (Request Body):**
- `bot_asset_id`: (Requerido) ID del BotAsset.
- `amount`: (Requerido) Cantidad de capital a añadir (puede ser negativo, siempre que el resultado en `cap_to_add` sea positivo).

**Ejemplo de Llamado:**
```bash
curl -X POST http://localhost:8000/api/proftview/assets/add-capital/ \
     -H "Content-Type: application/json" \
     -d '{"bot_asset_id": 1, "amount": 500.0}'
```

**Ejemplo de Respuesta:**
```json
{
  "message": "Capital added to asset successfully",
  "bot_asset_id": 1,
  "new_cap_to_add": 500.0,
  "total_capital_added": 5500.0
}
```

### Adición de Capital (Unassigned)
**Endpoint:** `POST /bot/add-capital/`

Permite añadir capital al campo `cap_no_asignado` de un bot y registrar una transacción.

**Cuerpo de la Petición (Request Body):**
- `bot_id`: (Requerido) ID del bot.
- `amount`: (Requerido) Cantidad de capital a añadir.
- `broker_id`: (Requerido) ID del broker relacionado.

**Ejemplo de Llamado:**
```bash
curl -X POST http://localhost:8000/api/proftview/bot/add-capital/ \
     -H "Content-Type: application/json" \
     -d '{"bot_id": 1, "amount": 1000.0, "broker_id": 1}'
```

**Ejemplo de Respuesta:**
```json
{
  "message": "Capital added successfully",
  "bot_id": 1,
  "new_cap_no_asignado": 1000.0,
  "total_capital_added": 5000.0
}
```
