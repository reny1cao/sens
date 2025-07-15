"""
Central registry for managing components and their lifecycle.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type

import structlog

from ..common.errors import NotFoundError, ValidationError
from ..interfaces import Pipeline, QueryExecutor, Retriever, SQLGenerator, Validator

logger = structlog.get_logger(__name__)


class ComponentType(str, Enum):
    """Types of components that can be registered."""

    RETRIEVER = "retriever"
    GENERATOR = "generator"
    VALIDATOR = "validator"
    EXECUTOR = "executor"
    PIPELINE = "pipeline"


@dataclass
class ComponentInfo:
    """Information about a registered component."""

    name: str
    component_type: ComponentType
    implementation_class: Type
    factory: Optional[Callable] = None
    singleton: bool = False
    instance: Optional[Any] = None
    config: Dict[str, Any] = field(default_factory=dict)


class ComponentRegistry:
    """
    Central registry for all components.

    This registry enables:
    - Component registration and discovery
    - Dependency injection
    - Singleton management
    - Configuration-based component creation
    """

    def __init__(self):
        self._components: Dict[str, ComponentInfo] = {}
        self._type_mapping = {
            ComponentType.RETRIEVER: Retriever,
            ComponentType.GENERATOR: SQLGenerator,
            ComponentType.VALIDATOR: Validator,
            ComponentType.EXECUTOR: QueryExecutor,
            ComponentType.PIPELINE: Pipeline,
        }

    def register(
        self,
        name: str,
        component_type: ComponentType,
        implementation_class: Type,
        factory: Optional[Callable] = None,
        singleton: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a component.

        Args:
            name: Unique component name
            component_type: Type of component
            implementation_class: Class implementing the component interface
            factory: Optional factory function for creating instances
            singleton: Whether to maintain a single instance
            config: Default configuration for the component
        """
        # Validate implementation only if not using factory
        # (factories handle their own validation)
        if not factory:
            expected_base = self._type_mapping.get(component_type)
            if expected_base and not issubclass(implementation_class, expected_base):
                raise ValidationError(
                    f"Component {name} must implement {expected_base.__name__}"
                )

        # Register component
        self._components[name] = ComponentInfo(
            name=name,
            component_type=component_type,
            implementation_class=implementation_class,
            factory=factory,
            singleton=singleton,
            config=config or {},
        )

        logger.info(
            "component_registered", component_type=component_type.value, name=name
        )

    def get(self, name: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Get a component instance.

        Args:
            name: Component name
            config: Optional configuration overrides

        Returns:
            Component instance
        """
        if name not in self._components:
            raise NotFoundError(f"Component not found: {name}")

        info = self._components[name]

        # Return singleton instance if available
        if info.singleton and info.instance:
            return info.instance

        # Create new instance
        merged_config = {**info.config}
        if config:
            merged_config.update(config)

        if info.factory:
            instance = info.factory(**merged_config)
        else:
            instance = info.implementation_class(**merged_config)

        # Store singleton instance
        if info.singleton:
            info.instance = instance

        return instance

    def get_by_type(
        self,
        component_type: ComponentType,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Get a component by type.

        Args:
            component_type: Type of component
            name: Optional specific component name
            config: Optional configuration overrides

        Returns:
            Component instance
        """
        # Find matching components
        matching = [
            info
            for info in self._components.values()
            if info.component_type == component_type
        ]

        if not matching:
            raise NotFoundError(f"No {component_type} components registered")

        # If name specified, find exact match
        if name:
            for info in matching:
                if info.name == name:
                    return self.get(name, config)
            raise NotFoundError(f"Component not found: {name}")

        # Return first matching component
        return self.get(matching[0].name, config)

    def list_components(
        self, component_type: Optional[ComponentType] = None
    ) -> Dict[str, ComponentInfo]:
        """
        List registered components.

        Args:
            component_type: Optional filter by type

        Returns:
            Dictionary of component info by name
        """
        if component_type:
            return {
                name: info
                for name, info in self._components.items()
                if info.component_type == component_type
            }
        return self._components.copy()

    def clear(self) -> None:
        """Clear all registered components."""
        self._components.clear()

    def unregister(self, name: str) -> None:
        """Unregister a component."""
        if name in self._components:
            del self._components[name]
            logger.info(f"Unregistered component: {name}")


# Global registry instance
component_registry = ComponentRegistry()
