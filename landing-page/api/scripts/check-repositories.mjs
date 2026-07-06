import { catalogRepository } from "../src/repositories/catalogRepository.mjs";
import { paymentProvidersRepository } from "../src/repositories/paymentProvidersRepository.mjs";

const providers = catalogRepository.listProviders();
const platformModels = catalogRepository.listPlatformModels();
const providerModels = catalogRepository.listProviderModels();
const channels = catalogRepository.listChannels();
const mappings = catalogRepository.listParameterMappings();
const paymentProviders = paymentProvidersRepository.list();

assertNonEmpty(providers, "providers");
assertNonEmpty(platformModels, "platform models");
assertNonEmpty(providerModels, "provider models");
assertNonEmpty(channels, "model channels");
assertNonEmpty(mappings, "parameter mappings");
assertNonEmpty(paymentProviders, "payment providers");

for (const model of platformModels) {
  assertString(model.id, "platform model id");
  assertString(model.name, `${model.id} name`);
  assertString(model.shortName, `${model.id} shortName`);
  assertString(model.modality, `${model.id} modality`);
  assertArray(model.schema, `${model.id} schema`);
  assertArray(model.useCases, `${model.id} useCases`);
}

for (const channel of channels) {
  assertString(channel.id, "channel id");
  assertString(channel.platformModelId, `${channel.id} platformModelId`);
  assertString(channel.providerId, `${channel.id} providerId`);
  assertString(channel.providerModelId, `${channel.id} providerModelId`);
  assertArray(channel.supports, `${channel.id} supports`);
  assertNumber(channel.costPrice, `${channel.id} costPrice`);
  assertNumber(channel.salePrice, `${channel.id} salePrice`);

  if (!catalogRepository.getPlatformModel(channel.platformModelId)) {
    throw new Error(`${channel.id} references missing platform model ${channel.platformModelId}.`);
  }

  if (!catalogRepository.getProvider(channel.providerId)) {
    throw new Error(`${channel.id} references missing provider ${channel.providerId}.`);
  }

  if (!catalogRepository.getProviderModel(channel.providerModelId)) {
    throw new Error(`${channel.id} references missing provider model ${channel.providerModelId}.`);
  }
}

for (const mapping of mappings) {
  assertString(mapping.channelId, "mapping channelId");
  assertString(mapping.platform, `${mapping.channelId} platform param`);
  assertString(mapping.transform, `${mapping.channelId} transform`);

  if (!catalogRepository.getChannel(mapping.channelId)) {
    throw new Error(`Mapping ${mapping.platform} references missing channel ${mapping.channelId}.`);
  }
}

for (const provider of paymentProviders) {
  assertString(provider.id, "payment provider id");
  assertString(provider.name, `${provider.id} name`);
  assertString(provider.kind, `${provider.id} kind`);
  assertString(provider.status, `${provider.id} status`);
  assertArray(provider.currencies, `${provider.id} currencies`);
  assertNumber(provider.minAmount, `${provider.id} minAmount`);
  assertNumber(provider.maxAmount, `${provider.id} maxAmount`);

  if (provider.currencies.length === 0) {
    throw new Error(`${provider.id} must support at least one currency.`);
  }
  if (provider.maxAmount < provider.minAmount) {
    throw new Error(`${provider.id} maxAmount must be greater than or equal to minAmount.`);
  }
}

console.log(
  `Checked memory repository contract: ${providers.length} provider(s), ${platformModels.length} model(s), ${channels.length} channel(s), ${paymentProviders.length} payment provider(s).`
);

function assertNonEmpty(value, label) {
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`Expected non-empty ${label}.`);
  }
}

function assertArray(value, label) {
  if (!Array.isArray(value)) {
    throw new Error(`Expected ${label} to be an array.`);
  }
}

function assertString(value, label) {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`Expected ${label} to be a non-empty string.`);
  }
}

function assertNumber(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Expected ${label} to be a finite number.`);
  }
}
